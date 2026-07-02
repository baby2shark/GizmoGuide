from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from app.agent.llm_client import ChatMessage, DeepSeekClient
from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.agent.recommend_agent import RecommendDeps, build_finisher_agent, build_recommend_agent
from app.agent.schemas import AgentResponse
from app.agent.state import ConversationState, long_term_memory_store, session_store
from app.config.settings import get_settings
from app.orchestrator.long_term_memory_extractor import extract_preference_memory, merge_profiles
from app.orchestrator.profile_extractor import extract_profile
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.long_term_memory import LongTermMemory
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse, RecommendationResult
from app.tools.product_tool import ProductTool
from app.tools.scoring_tool import ScoringTool
from app.tools.knowledge_search_tool import KnowledgeSearchTool
from app.tools.web_search_tool import WebSearchTool
from app.tracing import trace_span, trace_generation


class PurchaseDecisionAgent:
    def __init__(self, llm_client: DeepSeekClient | None = None):
        settings = get_settings()
        self.settings = settings
        self.llm_client = llm_client or DeepSeekClient(settings)
        self.product_tool = ProductTool()
        self.scoring_tool = ScoringTool()
        self.web_search_tool = WebSearchTool(settings)
        self.knowledge_search_tool = KnowledgeSearchTool(settings)

    def chat(self, request: ChatRequest) -> ChatResponse:
        with trace_span(
            "purchase_agent_chat",
            input_data={"message": request.message, "session_id": request.session_id},
        ) as (span, end_span):
            user_id = request.user_id or request.session_id
            memory = long_term_memory_store.get(user_id)
            state = session_store.get(request.session_id)
            state.user_id = user_id
            state.profile = merge_profiles(memory.profile_memory, state.profile)
            self._update_candidates(state, request.candidate_products)
            state.profile = extract_profile(request.message, state.profile)
            memory.preference_memory = extract_preference_memory(request.message, memory.preference_memory)
            memory.profile_memory = merge_profiles(memory.profile_memory, state.profile)
            state.messages.append({"role": "user", "content": request.message})

            scoring_result = self._try_scoring(state)

            if self.llm_client.enabled and (self.web_search_tool.enabled or self.knowledge_search_tool.enabled):
                try:
                    response = self._agent_loop_chat(request, state, scoring_result)
                    state.messages.append({"role": "assistant", "content": response.assistant_message})
                    end_span(output={"mode": response.mode, "answer_source": response.answer_source})
                    return response
                except Exception as exc:
                    fallback = self._fallback_chat(request, state, scoring_result)
                    fallback.agent_trace.append(f"agent_loop_failed:{type(exc).__name__}")
                    state.messages.append({"role": "assistant", "content": fallback.assistant_message})
                    end_span(output={"mode": fallback.mode, "answer_source": fallback.answer_source, "error": str(exc)}, level="ERROR")
                    return fallback

            if self.llm_client.enabled:
                try:
                    response = self._llm_chat(request, state, scoring_result)
                    state.messages.append({"role": "assistant", "content": response.assistant_message})
                    end_span(output={"mode": response.mode, "answer_source": response.answer_source})
                    return response
                except Exception as exc:
                    fallback = self._fallback_chat(request, state, scoring_result)
                    fallback.agent_trace.append(f"llm_failed:{type(exc).__name__}")
                    state.messages.append({"role": "assistant", "content": fallback.assistant_message})
                    end_span(output={"mode": fallback.mode, "answer_source": fallback.answer_source, "error": str(exc)}, level="ERROR")
                    return fallback

            fallback = self._fallback_chat(request, state, scoring_result)
            state.messages.append({"role": "assistant", "content": fallback.assistant_message})
            end_span(output={"mode": fallback.mode, "answer_source": fallback.answer_source})
            return fallback

    def handle(self, request: RecommendationRequest) -> RecommendationResponse:
        chat_response = self.chat(
            ChatRequest(
                session_id=f"recommendation-compat-{uuid4().hex}",
                user_id=request.user_id,
                message=request.user_message,
                candidate_products=request.candidate_products,
            )
        )
        return RecommendationResponse(
            need_clarification=chat_response.mode == "chat" and chat_response.recommendation is None,
            clarification_questions=[],
            user_profile=chat_response.user_profile,
            products=chat_response.products,
            recommendation=chat_response.recommendation,
            answer=chat_response.assistant_message,
            answer_source=chat_response.answer_source,
            agent_trace=chat_response.agent_trace,
        )

    def _update_candidates(self, state: ConversationState, candidate_products: list[str]) -> None:
        if not candidate_products:
            return
        with trace_span("product_lookup", input_data={"candidates": candidate_products}) as (span, end_span):
            products, missing = self.product_tool.get_products(candidate_products)
            if products:
                state.candidate_products = products
            end_span(output={"found": len(products), "missing": missing})

    def _try_scoring(self, state: ConversationState) -> RecommendationResult | None:
        if len(state.candidate_products) < 2:
            return None
        with trace_span("scoring_engine", input_data={"products": [p.name for p in state.candidate_products]}) as (span, end_span):
            try:
                result = self.scoring_tool.evaluate(state.candidate_products, state.profile)
                end_span(output={"winner": result.winner_name, "confidence": result.confidence})
                return result
            except Exception as exc:
                end_span(level="ERROR", output={"error": str(exc)})
                return None

    def _agent_loop_chat(
        self,
        request: ChatRequest,
        state: ConversationState,
        scoring_result: RecommendationResult | None,
    ) -> ChatResponse:
        with trace_span("agent_loop", input_data={"message": request.message}) as (agent_span, end_agent_span):
            agent = build_recommend_agent(self.settings)
            deps = RecommendDeps(
                web_search_tool=self.web_search_tool,
                knowledge_search_tool=self.knowledge_search_tool,
            )
            memory = self._get_long_term_memory(state)

            context_payload = {
                "candidate_products": [product.model_dump(mode="json") for product in state.candidate_products],
                "user_profile": state.profile.model_dump(mode="json"),
                "long_term_memory": memory.model_dump(mode="json"),
                "scoring_guardrail_result": scoring_result.model_dump(mode="json") if scoring_result else None,
            }
            prompt = (
                "当前已知信息（来自本地工具）：\n"
                + json.dumps(context_payload, ensure_ascii=False)
                + "\n\n用户最新消息：\n"
                + request.message
            )

            # pydantic-ai 负责工具循环、schema、参数校验和 tool_call 对齐。
            # request_limit 作为护栏：限制模型的请求轮数（一轮里并行调多个工具只算 1 次），
            # +1 是留给「拿到搜索结果后生成最终回答」的那一次请求，防止死循环/烧钱。
            round_limit = max(1, self.settings.agent_max_tool_rounds)
            trace = ["used_agent", "used_product_tool", "used_scoring_guardrail_tool"]

            with capture_run_messages() as run_messages:
                with trace_generation(
                    "agent_run",
                    model=self.settings.deepseek_model,
                    input_data=prompt,
                    metadata={"max_tool_rounds": round_limit},
                ) as (gen, end_gen):
                    try:
                        result = agent.run_sync(
                            prompt,
                            deps=deps,
                            message_history=state.agent_messages or None,
                            usage_limits=UsageLimits(request_limit=round_limit + 1),
                        )
                        agent_output: AgentResponse = result.output
                        state.agent_messages = result.all_messages()

                        usage_info = {}
                        if hasattr(result, "usage") and result.usage:
                            u = result.usage
                            usage_info = {
                                "prompt_tokens": getattr(u, "request_tokens", 0),
                                "completion_tokens": getattr(u, "response_tokens", 0),
                                "total_tokens": getattr(u, "total_tokens", 0),
                            }
                        end_gen(
                            output=agent_output.model_dump(mode="json"),
                            usage=usage_info if usage_info else None,
                        )
                    except UsageLimitExceeded:
                        # 触顶不丢弃证据：用无工具的收尾 agent，基于已搜到的信息直接作答。
                        agent_output = self._finish_without_tools(list(run_messages))
                        state.agent_messages = list(run_messages)
                        trace.append("tool_round_limit_reached")
                        end_gen(
                            output=agent_output.model_dump(mode="json"),
                            metadata_extra={"reason": "round_limit_reached"},
                        )

            trace.extend(deps.trace)
            final_text = (agent_output.reply or "").strip() or "我需要再了解一点你的购买需求。"

            # Use structured output to override scoring result if agent made a decision
            effective_scoring = scoring_result
            if agent_output.winner_id and agent_output.confidence > 0:
                effective_scoring = self._merge_agent_decision(scoring_result, agent_output, state)

            end_agent_span(output={
                "mode": "recommendation" if effective_scoring is not None else "chat",
                "agent_confidence": agent_output.confidence,
                "agent_winner": agent_output.winner_name,
            })
            return ChatResponse(
                session_id=state.session_id,
                user_id=memory.user_id,
                mode="recommendation" if effective_scoring is not None else "chat",
                assistant_message=final_text,
                user_profile=state.profile,
                long_term_memory=memory,
                products=state.candidate_products,
                recommendation=effective_scoring,
                answer_source="agent",
                agent_trace=trace,
            )

    def _merge_agent_decision(
        self,
        scoring_result: RecommendationResult | None,
        agent_output: AgentResponse,
        state: ConversationState,
    ) -> RecommendationResult | None:
        """Merge the agent's structured decision into the scoring result.

        If a scoring result exists, overlay the agent's winner/confidence/reasons.
        If no scoring result exists, synthesize one from the agent's decision.
        """
        if scoring_result is not None:
            # Overlay agent's judgment onto existing scoring
            score_by_id = {s.product_id: s for s in scoring_result.scores}
            winner_id = agent_output.winner_id if agent_output.winner_id in score_by_id else scoring_result.winner_id
            winner_name = score_by_id.get(winner_id, scoring_result.scores[0] if scoring_result.scores else None)
            return RecommendationResult(
                winner_id=winner_id,
                winner_name=winner_name.product_name if hasattr(winner_name, "product_name") else str(winner_name),
                confidence=max(0.0, min(1.0, agent_output.confidence or scoring_result.confidence)),
                scores=scoring_result.scores,
                key_reasons=agent_output.key_reasons or scoring_result.key_reasons,
                risks=agent_output.risks or scoring_result.risks,
                reversal_conditions=scoring_result.reversal_conditions,
                missing_information=agent_output.missing_information or scoring_result.missing_information,
            )
        # No scoring result (e.g. < 2 candidates) — synthesize minimal result
        return RecommendationResult(
            winner_id=agent_output.winner_id or "",
            winner_name=agent_output.winner_name or "",
            confidence=agent_output.confidence,
            scores=[],
            key_reasons=agent_output.key_reasons,
            risks=agent_output.risks,
            reversal_conditions=[],
            missing_information=agent_output.missing_information,
        )

    def _finish_without_tools(self, history: list[Any]) -> AgentResponse:
        with trace_generation(
            "finisher_agent",
            model=self.settings.deepseek_model,
            input_data="已达到联网搜索次数上限。请基于以上已经获取到的搜索信息，直接给出对比结论和推荐，不要再尝试搜索。",
            metadata={"reason": "round_limit_reached"},
        ) as (gen, end_gen):
            finisher = build_finisher_agent(self.settings)
            result = finisher.run_sync(
                "已达到联网搜索次数上限。请基于以上已经获取到的搜索信息，直接给出对比结论和推荐，不要再尝试搜索。",
                message_history=history or None,
            )
            agent_output: AgentResponse = result.output
            end_gen(output=agent_output.model_dump(mode="json"))
            return agent_output

    def _llm_chat(
        self,
        request: ChatRequest,
        state: ConversationState,
        scoring_result: RecommendationResult | None,
    ) -> ChatResponse:
        with trace_span("llm_chat", input_data={"message": request.message}) as (span, end_span):
            payload = {
                "current_user_message": request.message,
                "conversation_history": state.messages[-8:],
                "candidate_products": [product.model_dump(mode="json") for product in state.candidate_products],
                "user_profile": state.profile.model_dump(mode="json"),
                "scoring_guardrail_result": scoring_result.model_dump(mode="json") if scoring_result else None,
                "tooling_status": {
                    "product_tool": "available_mock_data",
                    "scoring_guardrail_tool": "available_reference_only",
                    "web_search_tool": "not_implemented_yet",
                    "local_kb_rag_tool": "not_implemented_yet",
                },
            }
            data = self.llm_client.chat_json(
                [
                    ChatMessage(role="system", content=AGENT_SYSTEM_PROMPT),
                    ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
                ],
                temperature=0.3,
            )
            mode = "recommendation" if data.get("mode") == "recommendation" else "chat"
            recommendation = None
            if mode == "recommendation" and scoring_result is not None:
                recommendation = self._recommendation_from_llm(data, scoring_result)

            end_span(output={"mode": mode, "answer_source": "llm"})
            return ChatResponse(
                session_id=state.session_id,
                user_id=self._memory_user_id(state),
                mode=mode,
                assistant_message=str(data.get("assistant_message") or data.get("summary") or "我需要再了解一点你的购买需求。"),
                user_profile=state.profile,
                long_term_memory=self._get_long_term_memory(state),
                products=state.candidate_products,
                recommendation=recommendation,
                answer_source="llm",
                agent_trace=["used_agent", "used_product_tool", "used_scoring_guardrail_tool", "used_deepseek"],
            )

    def _recommendation_from_llm(self, data: dict[str, Any], fallback: RecommendationResult) -> RecommendationResult:
        score_by_id = {score.product_id: score for score in fallback.scores}
        winner_id = data.get("winner_id") if data.get("winner_id") in score_by_id else fallback.winner_id
        winner_name = score_by_id[winner_id].product_name
        confidence = data.get("confidence", fallback.confidence)
        return RecommendationResult(
            winner_id=winner_id,
            winner_name=winner_name,
            confidence=max(0.0, min(1.0, float(confidence))),
            scores=fallback.scores,
            key_reasons=list(data.get("key_reasons") or fallback.key_reasons),
            risks=list(data.get("risks") or fallback.risks),
            reversal_conditions=list(data.get("reversal_conditions") or fallback.reversal_conditions),
            missing_information=list(data.get("missing_information") or fallback.missing_information),
        )

    def _fallback_chat(
        self,
        request: ChatRequest,
        state: ConversationState,
        scoring_result: RecommendationResult | None,
    ) -> ChatResponse:
        with trace_span("fallback_chat") as (span, end_span):
            if len(state.candidate_products) < 2:
                message = "你先选两款想比较的商品，我会先帮你做基础对比，然后继续聊你的预算和用途。"
                mode = "chat"
                recommendation = None
            elif scoring_result and self._profile_has_enough_signal(state):
                message = self._fallback_recommendation_message(scoring_result)
                mode = "recommendation"
                recommendation = scoring_result
            else:
                message = self._next_natural_question(state)
                mode = "chat"
                recommendation = None

            end_span(output={"mode": mode, "answer_source": "fallback"})
            return ChatResponse(
                session_id=state.session_id,
                user_id=self._memory_user_id(state),
                mode=mode,
                assistant_message=message,
                user_profile=state.profile,
                long_term_memory=self._get_long_term_memory(state),
                products=state.candidate_products,
                recommendation=recommendation,
                answer_source="fallback",
                agent_trace=["used_agent", "used_product_tool", "used_scoring_guardrail_tool", "llm_disabled"],
            )

    def _memory_user_id(self, state: ConversationState) -> str:
        return state.user_id or state.session_id

    def _get_long_term_memory(self, state: ConversationState) -> LongTermMemory:
        return long_term_memory_store.get(self._memory_user_id(state))

    def _profile_has_enough_signal(self, state: ConversationState) -> bool:
        profile = state.profile
        return bool(profile.budget and profile.primary_scenarios)

    def _next_natural_question(self, state: ConversationState) -> str:
        profile = state.profile
        names = " 和 ".join(product.name for product in state.candidate_products[:2])
        if not profile.budget:
            return f"这两款 {names} 我已经有基础参数了。你大概预算上限是多少？我会结合价格压力来判断。"
        if not profile.primary_scenarios:
            return f"预算我记下了。你主要拿它做什么？比如拍照、游戏、日常、办公，或者给长辈用。"
        return "我还想确认一个关键点：你更担心价格、维修风险、续航，还是拍照/性能体验？"

    def _fallback_recommendation_message(self, result: RecommendationResult) -> str:
        lines = [f"综合你目前说的信息，我更倾向推荐 {result.winner_name}。"]
        if result.key_reasons:
            lines.append("主要原因是：" + "；".join(result.key_reasons[:3]))
        if result.risks:
            lines.append("需要注意：" + "；".join(result.risks[:2]))
        lines.append("后面接入联网搜索和本地维修知识库后，我可以把评测、口碑和维修风险也纳入判断。")
        return "\n".join(lines)
