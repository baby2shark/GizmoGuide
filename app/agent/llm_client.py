from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.config.settings import Settings
from app.tracing import trace_generation


@dataclass
class ChatMessage:
    role: str
    content: str


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.2) -> dict[str, Any]:
        with trace_generation(
            "deepseek_raw_call",
            model=self.settings.deepseek_model,
            input_data=[{"role": m.role, "content": m.content[:500]} for m in messages],
            metadata={"temperature": temperature},
        ) as (gen, end_gen):
            if not self.settings.deepseek_api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

            payload = {
                "model": self.settings.deepseek_model,
                "messages": [message.__dict__ for message in messages],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
            data = self._post(payload)
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)

            usage_info = data.get("usage")
            usage = {}
            if usage_info:
                usage = {
                    "prompt_tokens": usage_info.get("prompt_tokens", 0),
                    "completion_tokens": usage_info.get("completion_tokens", 0),
                    "total_tokens": usage_info.get("total_tokens", 0),
                }
            end_gen(output=result, usage=usage if usage else None)
            return result

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.settings.llm_timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek network error: {exc.reason}") from exc

        return json.loads(raw)