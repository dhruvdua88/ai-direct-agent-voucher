# Reading / querying the books (all safe — reads never change data)

All reads are `TALLYREQUEST=Export`. Write the XML to a file and curl it exactly like a post, but nothing is
logged as a change. Set `SVEXPORTFORMAT` = `$$SysName:XML`, name the company verbatim, and give a date window.

## Trial Balance (group-level closing balances, honours dates)
```xml
<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Trial Balance</ID></HEADER>
 <BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY>
  <SVFROMDATE>20250401</SVFROMDATE><SVTODATE>20260331</SVTODATE>
 </STATICVARIABLES></DESC></BODY></ENVELOPE>
```
Parse `<DSPACCNAME>` (name) with `<DSPCLDRAMTA>` / `<DSPCLCRAMTA>` (closing Dr/Cr). Swap `<ID>` to
`Profit and Loss` for the P&L, or `Balance Sheet` (display-oriented, awkward to parse — prefer Trial Balance).

## Voucher Register (the workhorse for pulling transactions in a range)
```xml
<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Voucher Register</ID></HEADER>
 <BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY>
  <SVFROMDATE>20260301</SVFROMDATE><SVTODATE>20260331</SVTODATE>
 </STATICVARIABLES></DESC></BODY></ENVELOPE>
```
- The date filter is **sometimes ignored** — always re-filter in your parsing by the `<DATE>` each voucher
  returns. (`Day Book` as an `<ID>` often returns only the current date; prefer `Voucher Register`.)
- Match the real voucher element as `<VOUCHER[ >]`, not `<VOUCHER`, to avoid sub-tags like `<VOUCHERTYPENAME>`.
- `Narration` comes back **blank** in a Collection export but is present in Voucher Register — use this report.

## One ledger's entries / balance
Reading a single ledger is safe and fast. Either export `Ledger` with `<LEDGERNAME>` in the static variables,
or just read the closing figure off the Trial Balance above and filter to that account name. For a real,
multi-year book, the **Tally UI** (open the Ledger screen) shows opening/closing instantly and is the most
reliable — mention that to the user when they want a definitive balance.

## List ledgers (the fuzzy-match source — verify names before posting)
**Use the `List of Accounts` masters export** — `references/list-of-accounts.xml`. It returns every ledger
master as `<LEDGER NAME="…">` (plus groups, voucher types, etc.), completes fast even on a large book
(verified: 247 ledgers / 5 MB in seconds), and is safe because it dumps masters without computing balances.
Cache the response per session in `$TALLY_SESSION_DIR/_cache/` and feed it to `ledger.py match`.

**Do NOT use a TDL `<COLLECTION><TYPE>Ledger</TYPE>` request for this.** On real books it can stall the
single-threaded gateway (verified live: the collection hung Tally; the masters export did not). If the
masters export is ever unavailable, the fallback is the exploded Trial Balance below — it lists only accounts
with balances, so it's a weaker (but safe) name source.

## Ledger-wise trial balance (fallback name source + balance queries)
Add `<EXPLODEFLAG>Yes</EXPLODEFLAG>` to the Trial Balance static variables to get ledger rows
(`<DSPDISPNAME>`) under their groups instead of group totals only.

## List companies (works even before a company is loaded)
Use `references/list-companies.xml`. This is the preflight connectivity check.

## ⚠️ The one read that can hang Tally
Do **not** fetch closing balances for **all** ledgers at once on a real multi-year book — the gateway is
effectively single-threaded, so Tally replays all history to compute them and the whole instance freezes
(looks like a crash) while every other request queues behind it. Scope to one ledger/group (`<CHILDOF>` /
narrow `<FETCH>`), read it in the UI, or use this skill's cached `scripts/tally_report.py`
(pulls a range once into SQLite, then answers as SQL). A hung *read* is safe to force-kill — reads never
corrupt data; allow Tally's routine repair on reopen.
