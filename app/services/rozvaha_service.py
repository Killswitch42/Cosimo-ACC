"""
Rozvaha (balance sheet) line mapping.

Per vyhláška č. 500/2002 Sb., příloha č. 1 — zkrácený rozsah.
Separate maps for AKTIVA and PASIVA to avoid the naming collision in the
statutory form where both sections use "B.I", "B.II" etc.
"""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ledger_service import get_trial_balance
import uuid


AKTIVA_LINE_MAP: dict[str, list[str]] = {
    "B.I":   ["011", "012", "013", "014", "015", "019",
               "071", "072", "073", "074", "075", "079",
               "091"],                                     # Dlouhodobý nehmotný majetek
    "B.II":  ["021", "022", "025", "026", "029",
               "031", "032",
               "041", "042",
               "081", "082", "085", "086", "089",
               "092", "093"],                              # Dlouhodobý hmotný majetek
    "B.III": ["061", "062", "063", "065", "066", "067", "069",
               "043", "051", "052", "053",
               "094", "095", "096"],                      # Dlouhodobý finanční majetek
    "C.I":   ["111", "112", "119",
               "121", "122", "123", "124",
               "131", "132", "139",
               "191", "192", "193", "194", "195", "196"],  # Zásoby
    "C.II":  ["311", "312", "313", "314", "315",
               "335",
               "351", "352", "353", "354", "355", "358",
               "371", "374", "375", "376", "378",
               "381", "382", "385", "388",
               "346", "347",
               "341", "342",
               "391"],                                     # Pohledávky
    "C.III": ["251", "253", "255", "256", "259",
               "261", "291"],                              # Krátkodobý finanční majetek
    "C.IV":  ["211", "213", "221", "222", "223"],          # Peněžní prostředky
}

PASIVA_LINE_MAP: dict[str, list[str]] = {
    "A.I":   ["411", "412"],                               # Základní kapitál a ážio
    "A.II":  ["413", "414", "418", "419"],                 # Kapitálové fondy
    "A.III": ["421", "422", "423", "427"],                 # Fondy ze zisku
    "A.IV":  ["428", "429"],                               # Výsledek hospodaření minulých let
    "A.V":   ["431"],                                      # Výsledek hospodaření běžného období
    "B.I":   ["451", "453", "459"],                        # Rezervy
    "B.II":  ["461",
               "471", "472", "473", "474", "475", "478", "479",
               "481"],                                     # Dlouhodobé závazky
    "B.III": ["231", "232", "241", "249",
               "321", "322", "324", "325",
               "331", "333", "336",
               "341", "342", "343", "345",
               "361", "362", "364", "365", "366",
               "372", "379",
               "383", "384", "389"],                      # Krátkodobé závazky
    "C":     ["383", "384", "389"],                        # Časové rozlišení pasiv
}


async def generate_rozvaha(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> dict:
    """
    Generate the rozvaha using closing balances from the trial balance.
    Returns aktiva, pasiva, totals, and a balance check.
    """
    balances = await get_trial_balance(session, company_id, fiscal_period_id)
    balance_by_account = {b.account_number: b.closing_balance_czk for b in balances}

    def sum_prefixes(prefixes: list[str]) -> Decimal:
        total = Decimal("0.00")
        for acct, bal in balance_by_account.items():
            if any(acct.startswith(p) for p in prefixes):
                total += bal
        return total

    aktiva = {line: sum_prefixes(prefixes) for line, prefixes in AKTIVA_LINE_MAP.items()}
    pasiva = {line: sum_prefixes(prefixes) for line, prefixes in PASIVA_LINE_MAP.items()}

    aktiva_total = sum(aktiva.values())
    pasiva_total = sum(pasiva.values())

    return {
        "aktiva": aktiva,
        "aktiva_celkem": aktiva_total,
        "pasiva": pasiva,
        "pasiva_celkem": pasiva_total,
        "is_balanced": abs(aktiva_total - pasiva_total) <= Decimal("1.00"),
        "difference": aktiva_total - pasiva_total,
    }
