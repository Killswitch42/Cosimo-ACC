"""
Transaction classifier — asks Claude to suggest Czech accounts for transactions.
"""

import json
import time
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_client import call_claude, AIClientError
from app.models.classification_log import ClassificationLog

CLASSIFIER_SYSTEM_PROMPT = """
You are a Czech accounting expert specialising in podvojné účetnictví.
Respond only with valid JSON matching this schema:
{
  "debit_account": "string or null",
  "credit_account": "string or null",
  "vat_rate": "number or null",
  "cost_centre": "string or null",
  "reasoning": "string or null",
  "confidence": "number or null"
}
""".strip()


async def classify_transaction(
    session: AsyncSession,
    company_id: uuid.UUID,
    description: str,
    counterparty: str | None,
    amount_czk: Decimal | None,
    direction: str | None,
    classification_type: str = "FREE_TEXT",
) -> ClassificationLog:
    input_context = {
        "description": description,
        "counterparty": counterparty,
        "amount_czk": str(amount_czk) if amount_czk is not None else None,
        "direction": direction,
        "classification_type": classification_type,
    }
    user_message = (
        f"Classify this Czech accounting transaction:\n"
        f"Description: {description}\n"
        f"Counterparty: {counterparty or 'not specified'}\n"
        f"Amount (CZK): {amount_czk or 'not specified'}\n"
        f"Direction: {direction or 'not specified'}\n"
        "Respond only with JSON."
    )
    log = ClassificationLog(
        id=uuid.uuid4(),
        company_id=company_id,
        classification_type=classification_type,
        source_id=None,
        input_context=input_context,
        model_id="claude-sonnet-4-6",
    )
    try:
        raw_text, latency_ms = await call_claude(
            CLASSIFIER_SYSTEM_PROMPT,
            user_message,
            max_tokens=512,
        )
        log.latency_ms = latency_ms
        log.raw_response = {"text": raw_text}
        try:
            parsed = json.loads(raw_text)
            log.suggested_debit_account = parsed.get("debit_account")
            log.suggested_credit_account = parsed.get("credit_account")
            log.suggested_vat_rate = Decimal(str(parsed.get("vat_rate"))) if parsed.get("vat_rate") is not None else None
            log.suggested_cost_centre = parsed.get("cost_centre")
            log.reasoning = parsed.get("reasoning")
            log.confidence_score = Decimal(str(parsed.get("confidence"))) if parsed.get("confidence") is not None else None
        except json.JSONDecodeError:
            log.reasoning = f"Failed to parse Claude response: {raw_text}"
    except AIClientError as exc:
        log.reasoning = f"AI unavailable: {exc}"

    session.add(log)
    await session.flush()
    return log
