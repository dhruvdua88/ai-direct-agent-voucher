# Creating masters (ledger / stock item) when one is missing

Only create a master when a needed ledger genuinely doesn't exist — first list ledgers
(`references/reading.md`) to be sure, because a near-name typo creates a **duplicate** ledger rather than
reusing the real one. Confirm the **group** with the user in one line before creating (the group decides where
it lands in the P&L / Balance Sheet).

## Create a ledger
`REPORTNAME=All Masters`. **Include the inner `<NAME>` tag** (not just the `NAME="…"` attribute) or Tally
throws. Write to a file and curl it like any post; then it's ready to reference in a voucher.
```xml
<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>
 <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>
  <STATICVARIABLES><SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>
 <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
  <LEDGER NAME="Fuel" ACTION="Create">
   <NAME>Fuel</NAME>
   <PARENT>Indirect Expenses</PARENT>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
  </LEDGER>
 </TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>
```
Common parents: expenses → `Indirect Expenses` / `Direct Expenses`; income → `Indirect Incomes` /
`Sales Accounts`; a customer → `Sundry Debtors`; a vendor → `Sundry Creditors`; a bank → `Bank Accounts`;
cash → `Cash-in-Hand`; a loan → `Loans (Liability)`. `ISDEEMEDPOSITIVE=Yes` for expense/asset/debtor ledgers,
`No` for income/liability/creditor.

Success shows `<CREATED>1` (or `<ALTERED>1` if it already existed — `Create` on an existing ledger updates it).
A party ledger with GST needs more fields (GSTIN, registration type, state) — add them only if the user is
posting GST invoices; a plain expense/income/bank ledger needs just name + parent.

## Create a stock item (only if the user posts inventory)
```xml
<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>
 <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>
  <STATICVARIABLES><SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>
 <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
  <STOCKITEM NAME="Widget" ACTION="Create">
   <NAME>Widget</NAME>
   <PARENT>Primary</PARENT>
   <BASEUNITS>Nos</BASEUNITS>
  </STOCKITEM>
 </TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>
```
If `Nos` (the unit) doesn't exist yet, create a `<UNIT>` master first the same way. You **can't merge** two
stock items by renaming one to the other over the gateway (`ACTION="Alter"` to an existing name fails) — merge
in the UI if needed.
