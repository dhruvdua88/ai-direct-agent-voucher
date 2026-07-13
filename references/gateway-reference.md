# Gateway reference — transport, response schema, identifiers (authoritative)

Distilled from official Tally developer docs (sources at the bottom). Read this when you need to reason about
the protocol itself rather than a specific voucher shape.

## Transport
- Plain HTTP/1.0 server on the configured port (default **9000**), no path/auth. **POST** the raw XML envelope
  to `http://localhost:9000`; the body is the XML, the response is XML.
- **Single-threaded:** one request at a time, and it blocks the Tally UI while running. Never fire concurrent
  requests — serialise them. A heavy balance/report read can freeze Tally for minutes (see `reading.md`).
- **Every request targets the loaded company**, named **verbatim** in `<SVCURRENTCOMPANY>`. Omitting it uses
  the active company (fragile) — always set it explicitly for writes.
- Two request families share the `<ENVELOPE>` skeleton: `TALLYREQUEST=Import Data` (writes) and
  `TALLYREQUEST=Export` (reads).
- Native charset is **ISO-8859-1**. ASCII/Latin content posts fine as UTF-8 (verified live here); only
  non-Latin names need ISO-8859-1 re-encoding.

## The response counter block (how to read success/failure)
```xml
<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER>
 <BODY><DATA><IMPORTRESULT>
   <CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
   <LASTVCHID>119</LASTVCHID><LASTMID>0</LASTMID>
   <COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
 </IMPORTRESULT></DATA></BODY></ENVELOPE>
```
- `CREATED` / `ALTERED` / `DELETED` — what happened; exactly one is normally non-zero per voucher.
- `ERRORS` (and, on shape problems, `EXCEPTIONS` + `<LINEERROR>`) — **a voucher that errored is NOT written**
  even when `STATUS=1`. Success ⇒ (`CREATED`+`ALTERED`+`DELETED` ≥ 1) AND `ERRORS=0` AND `EXCEPTIONS=0`.
- `LASTVCHID` — internal id of the last voucher processed (traceability / read-back). `IGNORED` — silently
  skipped (often a duplicate-GUID skip).

## Identifiers — which one to key on
| Identifier | Owner | Use for dedupe/addressing? |
|---|---|---|
| **REMOTEID** | **You** assign it | **Yes** — the external idempotency key. Delete/Alter address the voucher by it. This skill stamps one on every voucher. |
| VCHKEY | Tally-internal GUID | No (appears on export; leave to Tally). |
| MASTERID | Tally-internal (= `LASTVCHID`) | Stable within one company, **not portable** across copies. |
| VOUCHERNUMBER | User/display | **No** — auto-numbering renumbers on import; never a dedupe key. |

**Create vs Alter idempotency:** whether `ACTION="Create"` with a known REMOTEID *alters* vs *duplicates* is
governed by the company's "overwrite when same GUID/REMOTEID" flag — sources disagree, so it's config
dependent. On this machine it **alters** (verified). The deterministic rule regardless of config: first push =
`Create`; any later update for the same key = `ACTION="Alter"` (send the full voucher, not a delta). The local
trail's `check` is the belt-and-braces guard against a second `Create`.

## Sources (official unless noted)
- Sample XML (import voucher, Trial Balance, sign convention) — help.tallysolutions.com/sample-xml/
- Case Study 1 (envelope + response counters) — help.tallysolutions.com/case-study-1/
- Case Study 2 (Create vs Alter) — help.tallysolutions.com/developer-reference/case-studies/case-study-2/
- "ISDEEMEDPOSITIVE" FAQ (Yes=Debit/negative, No=Credit/positive) — DeveloperReference/faq/8855
- Import Data FAQ (REMOTEID/GUID overwrite-vs-duplicate) — help.tallysolutions.com/tally-prime/import-data/import-data-faq/
- Import Data — Errors & Resolutions; "No Entries in Voucher" FAQ 6373 — LINEERROR / missing master
- MASTERID FAQs 7660 / 6191 / 6192 — id semantics
- Educational-mode date restriction — help.tallysolutions.com/.../work_in_educational_mode.htm
- Community: NoumaanAhamed/tally-prime-api-docs (OBJVIEW/inventory examples); icsoft.wiki Tally Invoice XML
  (invoice-view inventory + ACCOUNTINGALLOCATIONS pattern)

**Confidence:** sign convention, response tags, educational date lock, REMOTEID semantics are confirmed against
official pages. The nested GST-invoice `ACCOUNTINGALLOCATIONS.LIST` shape is community canon (official pages
show it only in fragments) — validate against your TallyPrime release before relying on GST auto-computation.
