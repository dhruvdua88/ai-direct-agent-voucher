# Batches, gap analysis, and proving a source before you post it

The single-voucher flow in SKILL.md scales to batches (a bank statement, an Excel of vouchers, a folder of
invoices) with three additions: a **review sheet**, **gap analysis before writing**, and **pacing + retry**
during the run. All learned the hard way at 650+ voucher scale (tally-integration quirks #11, #22, #37).

## 1. The review sheet (one gate for the whole batch)

Draft the batch as a CSV/XLSX — **one row per ledger LEG**, rows sharing a `remoteid` = one voucher:

```
remoteid | date | vtype | ledger | drcr | amount | narration
```
- `date`: DD-MM-YYYY, YYYY-MM-DD, or YYYYMMDD. `drcr`: Dr/Cr. `amount`: positive.
- Every `ledger` goes through the ledger guard (Rule 3) BEFORE it enters the sheet.
- REMOTEIDs: `ledger.py next-id` per voucher, or a deterministic scheme like `TV-BANK-<date>-<seq>`.

Show the user the sheet (or its summary: N vouchers, total Dr/Cr, date range, ledgers touched), get ONE yes
for the batch, then:

```bash
python "$LEDGER" sheet --company "$COMPANY" --file reviewed.csv
```
`sheet` validates balance per voucher, **skips anything already in the trail** (dedupe by date+vtype+legs),
and writes one ready-to-curl XML per voucher into the outbox — it never posts. It prints the file list.

## 2. Posting the batch: pace it, retry it, never hammer

- **One voucher per HTTP request**, sequential, **~0.5 s apart**. Large multi-voucher requests get cut off
  ("retry Split"; observed: 43-voucher request → only 7 created), and rapid-fire requests jam Tally.
- **"retry Split" / EXCEPTIONS on a known-good voucher is transient** — back off ~1 s and re-curl the SAME
  file, up to ~6 tries. Safe because REMOTEID is idempotent: a resend ALTERs, never duplicates.
- **If every voucher starts failing mid-run, the import engine is jammed** (often a modal dialog left open in
  the Tally window). Stop. Press **Esc** in Tally to clear any dialog; if it still fails, restart TallyPrime
  and reload the company. Then RESUME slowly (~1–2 s per voucher) — re-running the whole batch is safe
  (idempotent), the trail shows exactly which ones succeeded.
- `log` each response as you go (as in the single-voucher flow) so the trail stays complete even if the run
  is interrupted.

## 3. Gap analysis — write only what's missing (do this BEFORE building the sheet)

Tally does not dedupe, and the trail only knows what *this skill* posted. When entering data from a statement
into a book that may already have some of it:

1. Pull what's already there: `tally_report.py --report ledger --arg "<bank ledger>"` (cached, safe).
2. **Compare by NET DAILY movement, not line-by-line.** Owners consolidate: three same-day UPIs are often
   booked as ONE voucher. Per-line matching sees them as "missing", re-enters them, and double-counts (this
   once caused a 54-voucher double-count, caught only by reconciling the closing balance). Use:
   ```bash
   python "$REPORT" --company "$COMPANY" --from 20250401 --to 20260331 \
       --report bank-recon --arg "HDFC Bank" --statement stmt.csv
   ```
   Only dates where book-net ≠ statement-net need entries; enter the NET difference or the specific missing
   lines for that date, whichever matches how the owner books.
3. After posting, re-run the recon — it should return only the TOTAL row (zero mismatched dates).

## 4. From a PDF: prove the extraction is complete first

Read bank/invoice PDFs directly (vision); don't trust a generic table parser. Before anything from a PDF
enters a review sheet, **prove the extraction**:

- **Strongest check — the running balance.** Recompute it from the opening balance + each extracted line and
  match the printed running balance **row by row**. That pinpoints the exact row where extraction slipped;
  a grand total alone can hide two offsetting errors.
- No running balance? Tie to every control figure the doc prints: total debits, total credits, closing
  balance, transaction count.
- Password-protected tax PDFs (26AS/AIS/Form-16): password is usually **PAN-lowercase + DOB `DDMMYYYY`**.

Never post straight from a PDF — extraction → proof → review sheet → user's yes → post.

## 5. Reconcile at the end (the batch isn't done until this ties)

Whatever the source, finish by tying the book to it to the rupee: bank batches → `bank-recon` clean;
TDS entries → `tds-vs-26as` (26AS is the anchor for TDS credits; AIS is noisier — it can carry
Inactive/duplicate rows); trading → the broker's tax-P&L. A batch that posted with zero exceptions but
doesn't tie is still wrong.
