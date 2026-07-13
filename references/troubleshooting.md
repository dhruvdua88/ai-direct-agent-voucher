# Troubleshooting — every known failure mode and its fix

Success = the response has `CREATED`/`ALTERED`/`DELETED` ≥ 1 **and** `EXCEPTIONS = 0` **and** `ERRORS = 0`
and no `<LINEERROR>`. HTTP is always ~200 — the XML body is the only truth. `ledger.py log` computes this for
you. When it says `fail`, work down this list.

| Symptom in the response | Cause | Fix |
|---|---|---|
| `<LINEERROR>Ledger 'X' does not exist!</LINEERROR>` | ledger name wrong / not created | Copy the name **verbatim** from the book (trailing spaces, odd spelling are real). List ledgers (`references/reading.md`) to find the exact string, or create the ledger (`references/masters.md`) and confirm its group. |
| `<LINEERROR>Voucher Totals do not match!</LINEERROR>` | legs don't balance | `ledger.py build` refuses unbalanced vouchers, so this means a rounding/rate issue. Round to 2 dp; make one leg the balancing figure. |
| `EXCEPTIONS=1`, **no** `<LINEERROR>` | data-shape/feature problem Tally couldn't place | Almost always a **stock/GST invoice sent in the accounting shape**, or **Inventory (F11) is off**. Check both: use Invoice Voucher View for item invoices (`references/voucher-recipes.md`), and confirm F11 → Inventory is on. |
| `Voucher date is missing … retry Split` (but the date is present) | **Educational mode** (no active licence) | Educational mode accepts imports **only on the 1st, 2nd, or last day of a month**. Diagnostic: if 1st/2nd/last-day dates post but mid-month dates fail, it's the licence — activate it; don't edit XML. |
| every import fails with `retry Split` after a licence blip | licence jam — the import engine is stuck | Fix/reactivate the licence, then **reload the company** in Tally. Retry the *same* REMOTEID (idempotent) — don't mutate and re-send. |
| `retry Split` on ONE known-good voucher, licence fine | transient — Tally was busy | Back off ~1 s and re-curl the **same** file, up to ~6 tries (idempotent, never duplicates). Don't hammer faster. |
| every voucher fails mid-batch (was working, now nothing posts) | **import engine jammed** — usually a modal dialog left open in the Tally window after a sustained bulk run | Stop the batch. Press **Esc** in the Tally window to clear any dialog; if imports still fail, restart TallyPrime and reload the company. Resume slowly (~1–2 s/voucher) — re-running is idempotent and the trail shows what already succeeded. See `references/batch-and-recon.md`. |
| `Could not set 'SVCurrentCompany'` | company not loaded, or name mismatch | Load the company in Tally; copy its name **verbatim** into `$COMPANY`. (List of Companies works even with nothing loaded — use it to get the exact spelling.) |
| `Unknown Request` / malformed | a raw `&` (or `<`, `>`) in a name | XML-escape it (`&` → `&amp;`). `ledger.py build` escapes for you; only an issue if you hand-write XML. |
| empty response / connection refused | gateway off or Tally not running | Open TallyPrime, load the company, F1 → Settings → Connectivity → acts as **Both**, Port **9000**. |
| Tally UI frozen after a big read | the single-threaded hang | You fetched all-ledger balances or a huge register on a big book. Wait it out or force-close & reopen Tally; reads never corrupt data. Next time scope the read (see `references/reading.md`). |

## Idempotency & duplicates (the thing the trail protects against)
- Tally does **not** dedupe. Two `Create`s = two vouchers. The local trail's `check` catches an equivalent
  voucher *before* you post; always run it.
- Re-sending the **same REMOTEID** alters in place on this setup (empirically verified: `ALTERED=1`, no
  duplicate). If you ever see a duplicate appear on re-run, the company's "overwrite same-REMOTEID" flag is
  off — use `--action Alter` for updates (deterministic everywhere) and rely on the trail's `check` to prevent
  a second `Create`.
- **Delete vs Cancel:** `ACTION="Delete"` removes the voucher entirely; `ACTION="Cancel"` leaves a voided
  voucher that keeps its number (some audits prefer this). This skill deletes; switch to Cancel only if asked.

## Edit Log edition note
On **TallyPrime Edit Log**, every create/alter/delete is recorded in Tally's own edit log (audit trail) — so
gateway changes are fully traceable inside Tally too, independent of this skill's trail. Reassure the user:
nothing done via the gateway is hidden from Tally's audit history.

## Encoding
Tally natively speaks **ISO-8859-1**. Plain ASCII/Latin content (the overwhelming majority of Indian book
data) posts fine as the UTF-8 that `ledger.py` writes — verified live on this machine. If a name has non-Latin
characters and comes back garbled, re-save that one voucher's XML as ISO-8859-1 before curling.
