from __future__ import annotations

import json

from pydantic_ai import Agent

from app.agent.recommend_agent import _build_model
from app.config.settings import Settings
from app.orchestrator.long_term_memory_extractor import extract_preference_memory, merge_profiles
from app.orchestrator.profile_extractor import extract_profile
from app.schemas.long_term_memory import LongTermMemory, MemoryExtractionResult
from app.schemas.user_profile import UserProfile
from app.tracing import trace_generation, trace_span

MEMORY_AGENT_PROMPT = """你是 GizmoGuide 的长期记忆抽取子 Agent。

你的任务不是回答用户，而是从用户最新消息中判断哪些信息值得写入长期记忆。
长期记忆只包含两类：
1. preference_memory：用户稳定偏好，例如系统倾向、品牌偏好/排斥、喜欢/讨厌的特性、预算弹性、风险偏好、维修敏感度。
2. profile_memory：用户画像，例如预算、主要场景、预计使用年限、品牌/系统倾向、存储下限、重量上限。

要求：
- 只写用户明确表达或高度稳定可推断的信息，不要臆测。
- 保留已有记忆中的有效内容，并用新消息做增量更新。
- 如果用户只是临时比较某个商品，不要把它误写成长期偏好。
- 输出必须符合结构化 schema。
"""


class MemoryForkTool:
    """Fork a dedicated pydantic-ai sub-agent to extract long-term memory."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = settings.llm_enabled
        self._agent: Agent[None, MemoryExtractionResult] | None = None

    def extract(self, message: str, memory: LongTermMemory, session_profile: UserProfile) -> LongTermMemory:
        with trace_span("memory_fork_tool", input_data={"message": message[:200], "user_id": memory.user_id}) as (span, end_span):
            if not self.enabled:
                updated = self._fallback_extract(message, memory, session_profile)
                end_span(output={"mode": "fallback"})
                return updated

            payload = {
                "latest_user_message": message,
                "existing_long_term_memory": memory.model_dump(mode="json"),
                "current_session_profile": session_profile.model_dump(mode="json"),
            }
            try:
                with trace_generation(
                    "memory_extraction_agent",
                    model=self.settings.deepseek_model,
                    input_data=payload,
                    metadata={"agent": "long_term_memory_extractor"},
                ) as (gen, end_gen):
                    result = self._get_agent().run_sync(json.dumps(payload, ensure_ascii=False))
                    output = result.output
                    end_gen(output=output.model_dump(mode="json"))

                updated = LongTermMemory(
                    user_id=memory.user_id,
                    preference_memory=output.preference_memory,
                    profile_memory=merge_profiles(memory.profile_memory, output.profile_memory),
                )
                end_span(output={"mode": "subagent"})
                return updated
            except Exception as exc:  # noqa: BLE001
                updated = self._fallback_extract(message, memory, session_profile)
                end_span(output={"mode": "fallback", "error": str(exc)}, level="ERROR")
                return updated

    def _get_agent(self) -> Agent[None, MemoryExtractionResult]:
        if self._agent is None:
            self._agent = Agent(
                _build_model(self.settings),
                output_type=MemoryExtractionResult,
                system_prompt=MEMORY_AGENT_PROMPT,
            )
        return self._agent

    def _fallback_extract(self, message: str, memory: LongTermMemory, session_profile: UserProfile) -> LongTermMemory:
        profile_patch = extract_profile(message, session_profile)
        return LongTermMemory(
            user_id=memory.user_id,
            preference_memory=extract_preference_memory(message, memory.preference_memory),
            profile_memory=merge_profiles(memory.profile_memory, profile_patch),
        )
