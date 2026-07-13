# Voucher recipes — Dr/Cr direction, sign convention, ledger mapping

## The sign convention (the one footgun — `ledger.py build` handles it for you)
In the import XML each leg is `<ALLLEDGERENTRIES.LIST>` with:
- **Debit**  → `<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>` and a **negative** `<AMOUNT>`
- **Credit** → `<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>` and a **positive** `<AMOUNT>`

Every voucher's legs sum to zero. You never hand-write this — pass `--legs "Ledger:Dr:amt,Ledger:Cr:amt"`
to `ledger.py build` and it emits the correct signs. This table is just so you pick the right Dr/Cr side.

## Which side is which, per voucher type
| Type | Meaning | Dr (ISDEEMEDPOSITIVE=Yes) | Cr (No) |
|---|---|---|---|
| **Payment** | money OUT | the expense / party you paid | the bank / cash it left |
| **Receipt** | money IN | the bank / cash it arrived in | the income / party who paid |
| **Contra** | move between own accounts | destination bank/cash (money in) | source bank/cash (money out) |
| **Journal** | non-cash adjustment | the account debited | the account credited |

Examples in plain English → legs:
- *"₹5,000 cash spent on fuel"* → Payment: `Fuel:Dr:5000, Cash:Cr:5000`
- *"received ₹24,480 dividend into ICICI"* → Receipt: `ICICI Bank:Dr:24480, Dividend Received:Cr:24480`
- *"moved ₹1,00,000 from HDFC to Cash"* → Contra: `Cash:Dr:100000, HDFC Bank:Cr:100000`
- *"accrue ₹12,000 rent payable at year-end"* → Journal: `Rent:Dr:12000, Rent Payable:Cr:12000`

Multi-leg is fine (e.g. an expense split across heads, or a payment covering several bills) — list every leg;
they just have to balance.

## Common expense/income → ledger (confirm the exact ledger name exists in the company first)
Fuel/Petrol/Diesel → *Fuel* or *Vehicle Running Exp* (Indirect Expenses). Rent → *Rent* / *Rent Paid*.
Salaries → *Salaries*. Bank charges → *Bank Charges*. Professional fees paid → *Professional Charges* (watch
TDS u/s 194J). Interest income → *Interest Received*. Dividend → *Dividend Received*. Sales → the *Sales*
ledger; Purchases → *Purchase* ledger. **Copy the ledger's name verbatim from the book** — inventing a
near-name silently creates a duplicate ledger (quirks: ledger names carry trailing spaces / odd spellings).

## GST / inventory ("item") invoices are DIFFERENT — do not use the accounting shape
A stock/GST invoice (goods with quantities + CGST/SGST/IGST) must be posted in **Invoice Voucher View**, not
the Accounting Voucher View that `ledger.py build` produces. Requirements (quirks #15/#15a):
- `VCHTYPE="Sales"`/`"Purchase"` **with `OBJVIEW="Invoice Voucher View"` and `<ISINVOICE>Yes</ISINVOICE>`**
- party + GST legs go in voucher-level **`<LEDGERENTRIES.LIST>`** (note: *not* `ALLLEDGERENTRIES.LIST`)
- each goods line in **`<ALLINVENTORYENTRIES.LIST>`** with a `<BATCHALLOCATIONS.LIST>`
  (GODOWN `Main Location`, BATCH `Primary Batch`) and a nested `<ACCOUNTINGALLOCATIONS.LIST>` → the sales/
  purchase ledger.

Putting the party in `ALLLEDGERENTRIES.LIST` on a stock invoice returns `EXCEPTIONS=1` with **no LINEERROR**
— a silent rejection. For plain **accounting** Sales/Purchase (party + amount, no inventory), the normal
`ledger.py build` shape works fine — set `--vtype Sales`/`Purchase`.

### Working item-invoice XML (verified shape — adapt names/amounts, curl it, log it to the trail)
A GST purchase: 100 × Widget A @ ₹100 = ₹10,000 + ₹900 CGST + ₹900 SGST, party ₹11,800. Note the signs:
this is a Purchase, so goods + input GST are Dr (negative), party is Cr (positive) — flip all of them for a
Sales invoice. **RATE rule:** supply `rate = amount ÷ qty` AND the exact `<AMOUNT>` — amount+qty alone leaves
the rate blank (Tally does not back-calculate on import).
```xml
<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>
 <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>
  <STATICVARIABLES><SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>
 <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
  <VOUCHER REMOTEID="TV-PUR-20260301-001" VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
   <DATE>20260301</DATE><VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
   <PARTYLEDGERNAME>Vendor XYZ</PARTYLEDGERNAME><ISINVOICE>Yes</ISINVOICE>
   <NARRATION>Goods bought with GST - Vendor XYZ</NARRATION>
   <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>Widget A</STOCKITEMNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <RATE>100/Nos</RATE><AMOUNT>-10000</AMOUNT><ACTUALQTY>100 Nos</ACTUALQTY><BILLEDQTY>100 Nos</BILLEDQTY>
    <BATCHALLOCATIONS.LIST><GODOWNNAME>Main Location</GODOWNNAME><BATCHNAME>Primary Batch</BATCHNAME>
     <ACTUALQTY>100 Nos</ACTUALQTY><BILLEDQTY>100 Nos</BILLEDQTY><AMOUNT>-10000</AMOUNT></BATCHALLOCATIONS.LIST>
    <ACCOUNTINGALLOCATIONS.LIST><LEDGERNAME>Purchases</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
     <AMOUNT>-10000</AMOUNT></ACCOUNTINGALLOCATIONS.LIST>
   </ALLINVENTORYENTRIES.LIST>
   <LEDGERENTRIES.LIST><LEDGERNAME>Vendor XYZ</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>11800</AMOUNT></LEDGERENTRIES.LIST>
   <LEDGERENTRIES.LIST><LEDGERNAME>Input CGST</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-900</AMOUNT></LEDGERENTRIES.LIST>
   <LEDGERENTRIES.LIST><LEDGERNAME>Input SGST</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-900</AMOUNT></LEDGERENTRIES.LIST>
  </VOUCHER>
 </TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>
```
GST/TDS here are explicit ledger amounts (portable across Tally versions), not the auto-computation engine.
After posting, log it: `ledger.py log --action post --remoteid ... --response-file ...` like any voucher.

## The raw Payment XML (what `ledger.py build` produces — for reference/debugging)
```xml
<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>
 <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>
  <STATICVARIABLES><SVCURRENTCOMPANY>COMPANY</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>
 <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
  <VOUCHER REMOTEID="TV-PAY-20260331-001" VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
   <DATE>20260331</DATE><EFFECTIVEDATE>20260331</EFFECTIVEDATE>
   <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME><NARRATION>Fuel expense (cash)</NARRATION>
   <ALLLEDGERENTRIES.LIST><LEDGERNAME>Fuel</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-5000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
   <ALLLEDGERENTRIES.LIST><LEDGERNAME>Cash</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>5000.00</AMOUNT></ALLLEDGERENTRIES.LIST>
  </VOUCHER>
 </TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>
```
`ACTION="Create"` + a REMOTEID that already exists = Tally **alters** it in place (idempotent). That's why
re-running is safe and why amend is just "build with the same remoteid."
