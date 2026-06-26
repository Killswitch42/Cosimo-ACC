"""
xAI (Grok) wrapper for Medici Analytica.

Uses run_in_executor to wrap the synchronous OpenAI-compatible client in
order to avoid event loop conflicts with asyncpg.
"""

import asyncio
import time

import openai

from app.config import settings

MODEL_ID = "grok-3"
MAX_RETRIES = 3


class AIClientError(Exception):
    """Raised when xAI API is unavailable after all retries."""
    pass


async def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1024,
) -> tuple[str, int]:
    """
    Call xAI Grok and return (response_text, latency_ms).
    Retries up to MAX_RETRIES times with exponential backoff.
    Raises AIClientError after all retries exhausted.
    """
    if not settings.xai_api_key:
        raise AIClientError(
            "XAI_API_KEY is not set. "
            "Add it to .env to enable AI features."
        )

    client = openai.OpenAI(
        api_key=settings.xai_api_key,
        base_url="https://api.x.ai/v1",
    )
    loop = asyncio.get_event_loop()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            start = time.monotonic()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=MODEL_ID,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                )
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            text = response.choices[0].message.content
            return text, latency_ms

        except openai.RateLimitError as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)

        except openai.APIConnectionError as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)

        except openai.APIStatusError as e:
            if e.status_code >= 500:
                last_error = e
                await asyncio.sleep(2 ** attempt)
            else:
                raise AIClientError(f"xAI API error {e.status_code}: {e.message}")

    raise AIClientError(
        f"xAI API unavailable after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
