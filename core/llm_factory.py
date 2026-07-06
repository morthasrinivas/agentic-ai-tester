"""
LLM factory — returns either ChatOpenAI or ChatOllama depending on config.

Priority:
  1. OPENAI_API_KEY is set  → use ChatOpenAI (cloud, fast, best quality)
  2. Ollama is reachable     → use ChatOllama (local, no key needed)
  3. Neither                 → raise a clear error
"""

from __future__ import annotations
from langchain_core.language_models.chat_models import BaseChatModel


def _is_valid_openai_key(key: str) -> bool:
    """Return True only if the key looks like a real OpenAI secret (not a placeholder)."""
    return bool(key) and key.startswith("sk-") and len(key) > 30 and "..." not in key


def build_llm(temperature: float | None = None, json_mode: bool = False) -> BaseChatModel:
    """
    Build and return an LLM instance.

    Args:
        temperature: Override the default temperature from config.
        json_mode:   If True and using Ollama, enable Ollama's native JSON output
                     mode (used by Agent A and C for structured extraction).
                     Set to False for Agent B which generates free-form Python code.
    """
    import config

    temp = temperature if temperature is not None else config.LLM_TEMPERATURE

    if _is_valid_openai_key(config.OPENAI_API_KEY):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=temp,
            api_key=config.OPENAI_API_KEY,
        )

    # Try Ollama
    try:
        import requests
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3)
        resp.raise_for_status()
        from langchain_ollama import ChatOllama
        kwargs = dict(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=temp,
        )
        if json_mode:
            kwargs["format"] = "json"
        return ChatOllama(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"No LLM available.\n"
            f"  • Set OPENAI_API_KEY in .env  (cloud GPT)\n"
            f"  • Or ensure Ollama is running at {config.OLLAMA_BASE_URL}  (local)\n"
            f"  Ollama error: {exc}"
        ) from exc


def llm_provider_name() -> str:
    import config
    if _is_valid_openai_key(config.OPENAI_API_KEY):
        return f"OpenAI ({config.LLM_MODEL})"
    return f"Ollama ({config.OLLAMA_MODEL})"
