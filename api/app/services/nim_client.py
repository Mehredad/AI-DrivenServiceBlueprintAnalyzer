"""
NVIDIA NIM client — OpenAI-compatible endpoint for lightweight AI tasks.
Falls back to None if NIM_API_KEY is not configured, letting callers fall
back to Anthropic.
"""
import logging
from openai import AsyncOpenAI
from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


def get_nim_client() -> AsyncOpenAI | None:
    if not settings.nim_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.nim_api_key,
        base_url=settings.nim_base_url,
    )


async def nim_complete(
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str | None:
    """
    Call NIM with a system + user prompt. Returns the response text, or None
    if NIM is unavailable or the call fails (caller should fall back to Anthropic).
    """
    client = get_nim_client()
    if client is None:
        return None
    try:
        resp = await client.chat.completions.create(
            model=model or settings.nim_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        log.warning("NIM call failed, will fall back to Anthropic: %s", exc)
        return None
