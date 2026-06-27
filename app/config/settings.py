from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    llm_timeout_seconds: float
    bocha_api_key: str | None = None
    bocha_base_url: str = "https://api.bochaai.com"
    web_search_timeout_seconds: float = 20.0
    web_search_cache_ttl_seconds: float = 21600.0
    agent_max_tool_rounds: int = 4

    @property
    def llm_enabled(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def web_search_enabled(self) -> bool:
        return bool(self.bocha_api_key)


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "25")),
        bocha_api_key=os.getenv("BOCHA_API_KEY"),
        bocha_base_url=os.getenv("BOCHA_BASE_URL", "https://api.bochaai.com"),
        web_search_timeout_seconds=float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "20")),
        web_search_cache_ttl_seconds=float(os.getenv("WEB_SEARCH_CACHE_TTL_SECONDS", "21600")),
        agent_max_tool_rounds=int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "4")),
    )