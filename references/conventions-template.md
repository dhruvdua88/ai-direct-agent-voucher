# Company conventions — TEMPLATE

> One file per real company, saved as `$TALLY_SESSION_DIR/<company>__conventions.md` (next to the trail;
> it contains client data — keep it private, never commit it anywhere public). If this file exists for the
> active company, read it at preflight and follow it — it's what makes posted entries indistinguishable from
> the owner's own. Draft it by reading the prior year's vouchers (`tally_report.py --report daybook`), only
> when the user asks.

## 1. Identity
- Company string (verbatim): «COMPANY NAME»
- Financial year: «1-Apr-20xx to 31-Mar-20xx». Licence: «active / Educational (1st/2nd/last-day dates only)».

## 2. Ledger map — the ledgers actually posted to (names VERBATIM, quirks and all)
- Banks: «ledger name ↔ which bank/statement it maps to»
- Cash: «…»  Expenses: «per-head»  Income: «…»
- Parties / loans / capital / drawings: «…»
(Trailing spaces and misspellings are real — never "correct" a name; that creates a duplicate ledger.)

## 3. Voucher style (mirror exactly)
- Voucher type per transaction kind: «e.g. supplier bills as Journal + Payment, or direct Payment?»
- **Narration style** — copy the owner's phrasing verbatim, e.g. `«PAID TO <payee>»`,
  `«RENT PAID FOR <MON> <yy>»`, `«PERSONAL EXP»`.
- **Consolidation** — does the owner book same-day items individually or as ONE consolidated voucher?
  (Decides how gap analysis and new entries must be shaped — see `batch-and-recon.md` §3.)

## 4. Recurring posting recipes (exact Dr/Cr per known transaction)
- «Rent: Dr <ledger> / Cr <bank>, on the «2nd», narration "…"»
- «Salary TDS: booked net then grossed up per 26AS cut dates», etc.

## 5. Standing cautions for this book
- «e.g. two ledgers with confusingly similar names; a placeholder "-CHECK" ledger; prior-year opening
  mismatch of ₹X that is known and parked»
