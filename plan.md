# Plan — Close Czech Compliance Gaps (Medici Analytica)

Direction chosen 2026-08-18: audit DPPO / přiznání completeness / statutory mapping
against Czech law; add payroll. Baseline: **143 tests green** (via private PG cluster,
`TEST_DATABASE_URL` override in conftest).

## DONE (2026-08-18, suite 143→145 green)
- [x] **P0 — Rozvaha PASIVA double-count** fixed in `rozvaha_service.py`: 383/384 now
      live ONLY in `C` (časové rozlišení); 389 (dohadné účty pasivní) ONLY in `B.III`.
      Regression: `test_no_account_double_counted_within_a_side`.
- [x] **P0b — Sign-aware routing for dual-nature accounts** `341`/`342`: `generate_rozvaha`
      now loads `balance_type`, re-expresses each dual account debit-positive, and routes
      it to AKTIVA C.II (net debit → receivable) or PASIVA B.III (net credit → payable) —
      never both. Regression: `test_dual_nature_accounts_routed_by_balance_sign`.
      (Sign convention confirmed: `closing_balance_czk` is normal-balance-relative,
      set in `ledger_service.py:146-153`.)

## Backlog — future sessions (need user go-ahead / external resources)

### P1 — DPH přiznání completeness (`report_data_service.py:85-88`)
- row_3/4/9 intra-EU acquisitions (§16 ZDPH) — not populated
- row_5 import of goods — not populated
- row_20/21 intra-EU supplies (§64) — cross-check vs souhrnné hlášení
- row_26 domestic reverse charge (§92a) — verify B1 entries flow through

### P2 — XSD validation before ANY real filing (already flagged in code ⚠️)
- Download live XSD (DPHDP3, DPHKH1, DPHSHV) from adisspr.mfcr.cz
- Add `lxml.etree.XMLSchema` validation step + tests for dph/kh/sh XML services
- Verify element names / namespaces / attribute order against XSD

### P3 — DPPO annual return (`dppo_service.py` — currently decision-support only)
- Expand §25 non-deductible recognition beyond {513, 543}
- §23 adjustments, tax loss carry-forward, reliefs, advance payments
- Produce official DPDPPO EPO XML (deferred today)

### P4 — Payroll (Phase 3 item — NOT built)
- Employee/wage model, mzdové účty (521/524/331/336/342)
- Sociální + zdravotní pojištění, zálohová daň, ELDP / přehledy for ČSSZ + VZP

## Notes
- Code is honest about its simplifications (explicit ⚠️ markers) — a strength.
- Do NOT change Phase 01/02 tech-stack decisions.
- Run suite with: `TEST_DATABASE_URL=postgresql+asyncpg://medici:medici_dev_pass@127.0.0.1:55432/medici_accounting_test python -m pytest -q`
