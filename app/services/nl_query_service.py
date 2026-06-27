"""
Natural language query service.

Claude/Grok selects from a fixed menu of safe, parameterised query functions
(QUERY_TOOLS below); the service executes the actual DB lookup. This means
Grok never has raw SQL/database access — every possible query is auditable
and there is no SQL injection surface.

Flow:
  1. User asks a question (Czech or English)
  2. Grok picks which function(s) to call and with what parameters
  3. Service executes the function against the real database
  4. Result is sent back to Grok to phrase a natural-language answer
"""
import asyncio
import json
import uuid
from decimal import Decimal

import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import AlertRecord
from app.models.invoice import Invoice
from app.services.ai_client import MODEL_ID


# ── TOOL DEFINITIONS — fixed menu of safe queries Grok can invoke ──────────

QUERY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_vat_totals",
            "description": (
                "Get aggregated VAT totals (tax base and tax amount, by rate and direction) "
                "for a given period."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vat_period": {
                        "type": "string",
                        "description": "Format YYYY-MM, e.g. 2024-03",
                    },
                },
                "required": ["vat_period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unpaid_invoices",
            "description": (
                "List invoices that are posted but not yet paid (payment_date is null), "
                "optionally filtered by minimum amount."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["ISSUED", "RECEIVED"]},
                    "min_amount_czk": {
                        "type": "number",
                        "description": "Minimum gross amount in CZK",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_alerts_summary",
            "description": (
                "Get a count and summary of currently open compliance alerts, "
                "optionally filtered by severity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["BLOCKER", "WARNING", "INFO"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_balance",
            "description": (
                "Get the current closing balance of a specific Czech ledger account "
                "for a given fiscal period (by label, e.g. '2024')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Czech account number, e.g. '221' for bank",
                    },
                    "period_label": {
                        "type": "string",
                        "description": "Fiscal period label, e.g. '2024'",
                    },
                },
                "required": ["account_number", "period_label"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are an assistant embedded in Medici Analytica's Czech accounting system. "
    "Answer questions about the company's financial data by calling the provided tools "
    "to fetch real data — never invent numbers. "
    "Answer in the same language the user asked in (Czech or English). "
    "Be concise and concrete — cite specific numbers from the tool results. "
    "If a question cannot be answered with the available tools, say so clearly."
)


class NLQueryError(Exception):
    pass


async def _execute_tool(
    session: AsyncSession,
    company_id: uuid.UUID,
    tool_name: str,
    tool_input: dict,
) -> dict:
    if tool_name == "get_vat_totals":
        from app.services.vat_service import get_vat_period_totals
        totals = await get_vat_period_totals(session, company_id, tool_input["vat_period"])
        return {
            k: {"base": str(v["base"]), "tax": str(v["tax"]), "count": v["count"]}
            for k, v in totals.items()
        }

    elif tool_name == "get_unpaid_invoices":
        query = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.status == "posted",
            Invoice.payment_date.is_(None),
            Invoice.direction == tool_input["direction"],
        )
        if tool_input.get("min_amount_czk"):
            query = query.where(
                Invoice.total_gross_czk >= Decimal(str(tool_input["min_amount_czk"]))
            )
        result = await session.execute(query.limit(50))
        invoices = result.scalars().all()
        return {
            "count": len(invoices),
            "invoices": [
                {
                    "invoice_number": inv.invoice_number,
                    "counterparty": inv.counterparty_name,
                    "amount_czk": str(inv.total_gross_czk),
                    "due_date": str(inv.due_date) if inv.due_date else None,
                }
                for inv in invoices
            ],
        }

    elif tool_name == "get_open_alerts_summary":
        query = select(AlertRecord).where(
            AlertRecord.company_id == company_id,
            AlertRecord.status == "open",
        )
        if tool_input.get("severity"):
            query = query.where(AlertRecord.severity == tool_input["severity"])
        result = await session.execute(query)
        alerts = result.scalars().all()
        return {
            "count": len(alerts),
            "alerts": [
                {"title": a.title, "severity": a.severity} for a in alerts[:20]
            ],
        }

    elif tool_name == "get_account_balance":
        from app.services.ledger_service import get_account_balance
        from app.services.report_data_service import get_period_by_label
        period = await get_period_by_label(session, company_id, tool_input["period_label"])
        balance = await get_account_balance(
            session, company_id, period.id, tool_input["account_number"]
        )
        if not balance:
            return {"error": f"No balance found for account {tool_input['account_number']}"}
        return {
            "account_number": tool_input["account_number"],
            "closing_balance_czk": str(balance.closing_balance_czk),
            "period_debit_czk": str(balance.period_debit_czk),
            "period_credit_czk": str(balance.period_credit_czk),
        }

    return {"error": f"Unknown tool: {tool_name}"}


async def ask_question(
    session: AsyncSession,
    company_id: uuid.UUID,
    question: str,
) -> str:
    """
    Sends the question to Grok with tool definitions, executes whichever
    tool(s) it selects, and returns the final natural-language answer.
    """
    if not settings.xai_api_key:
        raise NLQueryError("XAI_API_KEY not configured.")

    client = openai.OpenAI(
        api_key=settings.xai_api_key,
        base_url="https://api.x.ai/v1",
    )
    loop = asyncio.get_event_loop()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    max_rounds = 3
    for _ in range(max_rounds):
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=MODEL_ID,
                max_tokens=1024,
                tools=QUERY_TOOLS,
                messages=messages,
            ),
        )

        choice = response.choices[0]

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            return choice.message.content or "Nepodařilo se získat odpověď."

        # Add assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": choice.message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ],
        })

        # Execute each tool and add results
        for tc in choice.message.tool_calls:
            tool_input = json.loads(tc.function.arguments)
            result_data = await _execute_tool(session, company_id, tc.function.name, tool_input)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result_data, ensure_ascii=False),
            })

    return "Nepodařilo se získat odpověď po maximálním počtu pokusů."
