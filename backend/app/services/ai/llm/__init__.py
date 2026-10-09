from app.services.ai.llm.base import LLMClient
from app.services.ai.llm.gemini import GeminiClient
from app.services.ai.llm.nvidia import NvidiaClient
from app.services.ai.llm.mock import MockLLM
from app.core.config import settings


def get_llm_client() -> LLMClient:
    """Factory to retrieve configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        return GeminiClient()
    elif provider in ("nvidia", "nim"):
        return NvidiaClient()
    return MockLLM()


__all__ = ["LLMClient", "GeminiClient", "NvidiaClient", "MockLLM", "get_llm_client"]
