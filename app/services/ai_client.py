"""
Anthropic SDK wrapper for Medici Analytica.

Uses run_in_executor to wrap the synchronous Anthropic client in order to
avoid event loop conflicts with asyncpg — both use async but the sync client
is safer in this context.
"""

import asyncio
import time

import anthropic

from app.config import settings

MODEL_ID = "claude-sonnet-4-6"
MAX_RETRIES = 3


class AIClientError(Exception):
    """Raised when Claude API is unavailable after all retries."""
    pass


async def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1024,
) -> tuple[str, int]:
    """
    Call Claude and return (response_text, latency_ms).
    Retries up to MAX_RETRIES times with exponential backoff.
    Raises AIClientError after all retries exhausted.
    """
    if not settings.anthropic_api_key:
        raise AIClientError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to .env to enable AI features."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    loop = asyncio.get_event_loop()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            start = time.monotonic()
            response = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model=MODEL_ID,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            text = response.content[0].text
            return text, latency_ms

        except anthropic.RateLimitError as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)

        except anthropic.APIConnectionError as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)

        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last_error = e
                await asyncio.sleep(2 ** attempt)
            else:
                raise AIClientError(f"Claude API error {e.status_code}: {e.message}")

    raise AIClientError(
        f"Claude API unavailable after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
