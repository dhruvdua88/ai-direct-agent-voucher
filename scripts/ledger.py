"""
ledger.py -- the local memory + XML builder for the tally-voucher skill.

It does NOT talk to Tally. Its two jobs:
  1. Build correct voucher/delete XML (handles the Dr/Cr sign trap for you) -> you curl it.
  2. Keep a per-company trail (JSON = source of truth, Excel = human-readable mirror) so nothing
     is double-posted and every action from the session is retrievable/reversible.

Posting stays curl-first: this only prepares XML and records what happened after curl runs.

Subcommands
  next-id   generate a fresh, unique REMOTEID for a (date, vtype)
  check     has an equivalent voucher already been posted? (dedupe by date+vtype+legs)
  match     fuzzy-match a proposed ledger name against the company's existing ledgers
            (feed it the curl'd LedgerList XML) -> EXACT / CLOSE candidates / NONE
  build     write a ready-to-curl Create/Alter voucher XML; prints its path
  build-del write a ready-to-curl Delete XML for an existing REMOTEID
  log       record an action after curl (parses Tally's XML response for created/altered/deleted/exceptions);
            works for vouchers AND masters (--action create-ledger, vtype/date optional)
  list      print the trail (optionally --session current)
  sessions  session-keyed JSON audit view: per session -> when, what was created/altered/deleted
  find      print the stored record for a REMOTEID (gives you date+vtype to delete/alter)

Legs format (repeatable): "Ledger Name:Dr:5000.00,Other Ledger:Cr:5000.00"
  Dr => ISDEEMEDPOSITIVE=Yes, negative AMOUNT;  Cr => No, positive AMOUNT  (quirks #17)

State dir: $TALLY_SESSION_DIR or ./tally-session/ . One JSON + one XLSX per company.
Deps: openpyxl (for the Excel mirror). JSON works without it.
"""
import sys, os, re, json, argparse, hashlib, datetime
from xml.sax.saxutils import escape

STATE_DIR = os.environ.get("TALLY_SESSION_DIR") or os.path.join(os.getcwd(), "tally-session")
SESSION_ID = datetime.datetime.now().strftime("%Y%m%d-%H%M")


def _safe(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_") or "company"

def _paths(company):
    os.makedirs(STATE_DIR, exist_ok=True)
    base = os.path.join(STATE_DIR, _safe(company))
    return base + "__trail.json", base + "__trail.xlsx"

def _load(company):
    j, _ = _paths(company)
    if os.path.exists(j):
        with open(j, encoding="utf-8") as f:
            return json.load(f)
    return []

def _parse_legs(s):
    """'Ledger:Dr:5000,Cash:Cr:5000' -> [('Ledger','Dr',5000.0),('Cash','Cr',5000.0)]"""
    out = []
    for chunk in [c for c in s.split(",") if c.strip()]:
        ledger, dc, amt = chunk.rsplit(":", 2)          # ledger name may contain no ':'
        dc = "Dr" if dc.strip().lower().startswith("d") else "Cr"
        out.append((ledger.strip(), dc, abs(float(str(amt).replace(",", "").strip()))))
    return out

def _legs_hash(date, vtype, legs):
    canon = f"{date}|{vtype.lower()}|" + ";".join(
        sorted(f"{l.strip().lower()}:{dc}:{a:.2f}" for l, dc, a in legs))
    return hashlib.sha1(canon.encode()).hexdigest()[:12]

def _balanced(legs):
    dr = sum(a for _, dc, a in legs if dc == "Dr")
    cr = sum(a for _, dc, a in legs if dc == "Cr")
    return abs(dr - cr) < 0.005, dr, cr


# ------------------------------------------------------------------ XML builders
def _leg_xml(ledger, dc, amount):
    dp = "Yes" if dc == "Dr" else "No"
    amt = -amount if dc == "Dr" else amount             # quirks #17
    return (f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledger)}</LEDGERNAME>"
            f"<ISDEEMEDPOSITIVE>{dp}</ISDEEMEDPOSITIVE><AMOUNT>{amt:.2f}</AMOUNT></ALLLEDGERENTRIES.LIST>")

def build_voucher_xml(company, remoteid, vtype, date, narration, legs, action="Create"):
    ok, dr, cr = _balanced(legs)
    if not ok:
        sys.exit(f"REFUSING to build unbalanced voucher {remoteid}: Dr {dr:.2f} != Cr {cr:.2f}")
    body = "".join(_leg_xml(l, dc, a) for l, dc, a in legs)
    vch = (f'<VOUCHER REMOTEID="{escape(remoteid)}" VCHTYPE="{escape(vtype)}" ACTION="{action}" '
           f'OBJVIEW="Accounting Voucher View"><DATE>{date}</DATE><EFFECTIVEDATE>{date}</EFFECTIVEDATE>'
           f'<VOUCHERTYPENAME>{escape(vtype)}</VOUCHERTYPENAME><NARRATION>{escape(narration)}</NARRATION>{body}</VOUCHER>')
    return (f'<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>'
            f'<REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES>'
            f'<SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>'
            f'<REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">{vch}</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>')

def build_delete_xml(company, remoteid, vtype, date):
    vch = (f'<VOUCHER REMOTEID="{escape(remoteid)}" VCHTYPE="{escape(vtype)}" ACTION="Delete">'
           f'<DATE>{date}</DATE><VOUCHERTYPENAME>{escape(vtype)}</VOUCHERTYPENAME></VOUCHER>')
    return (f'<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>'
            f'<REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES>'
            f'<SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>'
            f'<REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">{vch}</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>')

def _write_xml(company, remoteid, xml):
    outbox = os.path.join(STATE_DIR, "_outbox")
    os.makedirs(outbox, exist_ok=True)
    p = os.path.join(outbox, f"{_safe(remoteid)}.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(xml)
    return p


# ------------------------------------------------------------------ Excel mirror
def _rewrite_xlsx(company):
    try:
        import openpyxl
    except ImportError:
        return  # JSON still written; Excel mirror is best-effort
    _, x = _paths(company)
    recs = _load(company)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trail"
    cols = ["seq", "timestamp", "session", "action", "status", "remoteid", "vtype", "date",
            "narration", "legs", "created", "altered", "deleted", "exceptions", "error"]
    ws.append(cols)
    for r in recs:
        t = r.get("tally", {})
        legs = " / ".join(f"{dc} {l} {a:,.2f}" for l, dc, a in r.get("legs", []))
        # guard against Excel treating a leading =,+,-,@ as a formula (quirks #21)
        if legs and legs[0] in "=+-@":
            legs = " " + legs
        ws.append([r.get("seq"), r.get("ts"), r.get("session"), r.get("action"), r.get("status"),
                   r.get("remoteid"), r.get("vtype"), r.get("date"), r.get("narration"), legs,
                   t.get("created"), t.get("altered"), t.get("deleted"), t.get("exceptions"), t.get("error")])
    for c in ws.columns:
        w = max((len(str(v.value)) if v.value is not None else 0) for v in c)
        ws.column_dimensions[c[0].column_letter].width = min(max(w + 2, 8), 60)
    wb.save(x)


# ------------------------------------------------------------------ commands
def cmd_next_id(a):
    recs = _load(a.company)
    prefix = {"payment": "PAY", "receipt": "RCT", "contra": "CON", "journal": "JRN",
              "sales": "SAL", "purchase": "PUR"}.get(a.vtype.lower(), a.vtype[:3].upper())
    stem = f"TV-{prefix}-{a.date}-"
    used = {r["remoteid"] for r in recs if str(r.get("remoteid", "")).startswith(stem)}
    n = 1
    while f"{stem}{n:03d}" in used:
        n += 1
    print(f"{stem}{n:03d}")

def cmd_match(a):
    """Fuzzy-match a proposed ledger name against the ledgers Tally actually has.
    Input: --ledgers-xml = the curl'd response of a SAFE report export (never a TDL ledger
    collection - those can hang the gateway). Two supported shapes, tried in order:
      1. 'List of Accounts' masters export  -> <LEDGER NAME="..."> attributes (the full chart)
      2. 'Trial Balance' with EXPLODEFLAG   -> <DSPDISPNAME> rows (accounts with balances)
    Never guess a ledger: EXACT -> use it verbatim; CLOSE -> ask the user which; NONE -> ask before creating."""
    import difflib
    import html
    with open(a.ledgers_xml, encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    names = re.findall(r'<LEDGER NAME="([^"]*)"', txt)          # masters export (preferred)
    if not names:
        names = re.findall(r"<DSPDISPNAME>([^<]+)</DSPDISPNAME>", txt)   # exploded trial balance
    if not names:
        names = re.findall(r"<NAME[^>]*>([^<]+)</NAME>", txt)   # last resort: bare NAME tags
    names = sorted({html.unescape(n) for n in (x.strip() for x in names) if n}, key=str.lower)
    if not names:
        print("NO-LEDGERS: could not parse any ledger names from the XML - check the collection request.")
        return
    target = a.name.strip()
    for n in names:
        if n.lower() == target.lower():
            print(f"EXACT: {n}")          # verbatim spelling from the book - use THIS string
            if n != target:
                print(f"note: differs from your input only in case/spacing - post with {n!r} verbatim.")
            return
    scored = []
    for n in names:
        s = difflib.SequenceMatcher(None, target.lower(), n.lower()).ratio()
        if target.lower() in n.lower() or n.lower() in target.lower():
            s = max(s, 0.85)              # containment ("HDFC" vs "HDFC Bank") is a strong signal
        scored.append((s, n))
    top = [(s, n) for s, n in sorted(scored, reverse=True) if s >= 0.6][:5]
    if top:
        print(f"CLOSE: no exact match for {target!r}; nearest existing ledgers:")
        for s, n in top:
            print(f"  {s:.0%}  {n}")
        print("Ask the user which to use - or whether to create a new one. Do NOT pick silently.")
    else:
        print(f"NONE: nothing similar to {target!r} among {len(names)} ledgers. "
              f"Creating it needs the user's explicit yes (name + group).")


def cmd_check(a):
    legs = _parse_legs(a.legs)
    h = _legs_hash(a.date, a.vtype, legs)
    for r in _load(a.company):
        if r.get("hash") == h and r.get("action") in ("post", "alter") and r.get("status") == "ok":
            print(f"DUPLICATE: already posted as {r['remoteid']} (seq {r['seq']}, {r['ts']}). "
                  f"Re-posting the SAME remoteid ALTERs in place; a NEW remoteid would create a 2nd copy.")
            return
    print("NEW: no equivalent voucher in the trail - safe to create.")

def cmd_build(a):
    legs = _parse_legs(a.legs)
    xml = build_voucher_xml(a.company, a.remoteid, a.vtype, a.date, a.narration or "", legs, a.action)
    print(_write_xml(a.company, a.remoteid, xml))

def cmd_build_del(a):
    xml = build_delete_xml(a.company, a.remoteid, a.vtype, a.date)
    print(_write_xml(a.company, a.remoteid + "-DEL", xml))

def _extract(resp_text):
    g = lambda tag: int((re.search(fr"<{tag}>(\d+)", resp_text) or [0, 0])[1])
    le = re.search(r"<LINEERROR>(.*?)</LINEERROR>", resp_text or "", re.S)
    return {"created": g("CREATED"), "altered": g("ALTERED"), "deleted": g("DELETED"),
            "exceptions": g("EXCEPTIONS"), "errors": g("ERRORS"),
            "error": (le.group(1).strip()[:160] if le else "")}

def cmd_log(a):
    recs = _load(a.company)
    resp = ""
    if a.response_file and os.path.exists(a.response_file):
        with open(a.response_file, encoding="utf-8", errors="ignore") as f:
            resp = f.read()
    elif a.response:
        resp = a.response
    t = _extract(resp)
    legs = _parse_legs(a.legs) if a.legs else []
    done = (t["created"] + t["altered"] + t["deleted"]) > 0 and t["exceptions"] == 0 and t["errors"] == 0
    rec = {
        "seq": (recs[-1]["seq"] + 1) if recs else 1,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "session": SESSION_ID,
        "action": a.action,
        "status": "ok" if done else "fail",
        "remoteid": a.remoteid,
        "vtype": a.vtype or "",
        "date": a.date or "",
        "narration": a.narration or "",
        "legs": [[l, dc, amt] for l, dc, amt in legs],
        "hash": _legs_hash(a.date, a.vtype, legs) if (legs and a.date and a.vtype) else "",
        "tally": t,
    }
    recs.append(rec)
    j, _ = _paths(a.company)
    with open(j, "w", encoding="utf-8") as f:
        json.dump(recs, f, indent=1, ensure_ascii=False)
    _rewrite_xlsx(a.company)
    print(f"logged seq {rec['seq']}: {a.action} {a.remoteid} -> {rec['status']} "
          f"(created={t['created']} altered={t['altered']} deleted={t['deleted']} exceptions={t['exceptions']})"
          + (f"  ERROR: {t['error']}" if t['error'] else ""))

def cmd_list(a):
    recs = _load(a.company)
    if a.session == "current":
        recs = [r for r in recs if r.get("session") == SESSION_ID]
    if not recs:
        print("(trail empty)")
        return
    for r in recs:
        legs = " / ".join(f"{dc} {l} {a2:,.0f}" for l, dc, a2 in r.get("legs", []))
        print(f"  #{r['seq']:>3} {r['ts'][11:16]} {r['action']:6} {r['status']:4} "
              f"{r['remoteid']:22} {r['vtype']:8} {r['date']} | {legs}")
    j, x = _paths(a.company)
    print(f"\nJSON: {j}\nXLSX: {x}")

def cmd_sessions(a):
    """Session-keyed audit view: one JSON object per session with timestamps and what happened."""
    recs = _load(a.company)
    sessions = {}
    for r in recs:
        s = sessions.setdefault(r.get("session", "?"), {
            "started": r["ts"], "ended": r["ts"], "actions": 0,
            "created": [], "altered": [], "deleted": [], "failed": [],
        })
        s["ended"] = r["ts"]
        s["actions"] += 1
        entry = {"seq": r["seq"], "ts": r["ts"], "action": r["action"], "remoteid": r["remoteid"],
                 "vtype": r.get("vtype", ""), "date": r.get("date", ""),
                 "narration": r.get("narration", ""),
                 "legs": [f"{dc} {l} {amt:,.2f}" for l, dc, amt in r.get("legs", [])]}
        if r.get("status") != "ok":
            s["failed"].append({**entry, "error": r.get("tally", {}).get("error", "")})
        elif r.get("tally", {}).get("deleted"):
            s["deleted"].append(entry)
        elif r.get("tally", {}).get("altered"):
            s["altered"].append(entry)
        else:
            s["created"].append(entry)
    print(json.dumps(sessions, indent=1, ensure_ascii=False))


def cmd_find(a):
    for r in _load(a.company):
        if r.get("remoteid") == a.remoteid:
            print(json.dumps(r, ensure_ascii=False, indent=1))
            return
    print(f"not found: {a.remoteid}")


def main():
    ap = argparse.ArgumentParser(description="Local trail + XML builder for the tally-voucher skill.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("next-id"); p.add_argument("--company", required=True); p.add_argument("--date", required=True); p.add_argument("--vtype", required=True); p.set_defaults(fn=cmd_next_id)
    p = sub.add_parser("check"); p.add_argument("--company", required=True); p.add_argument("--date", required=True); p.add_argument("--vtype", required=True); p.add_argument("--legs", required=True); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("match"); p.add_argument("--company", required=True); p.add_argument("--name", required=True); p.add_argument("--ledgers-xml", dest="ledgers_xml", required=True); p.set_defaults(fn=cmd_match)
    p = sub.add_parser("build"); p.add_argument("--company", required=True); p.add_argument("--remoteid", required=True); p.add_argument("--vtype", required=True); p.add_argument("--date", required=True); p.add_argument("--narration"); p.add_argument("--legs", required=True); p.add_argument("--action", default="Create"); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("build-del"); p.add_argument("--company", required=True); p.add_argument("--remoteid", required=True); p.add_argument("--vtype", required=True); p.add_argument("--date", required=True); p.set_defaults(fn=cmd_build_del)
    p = sub.add_parser("log"); p.add_argument("--company", required=True); p.add_argument("--action", required=True); p.add_argument("--remoteid", required=True); p.add_argument("--vtype"); p.add_argument("--date"); p.add_argument("--narration"); p.add_argument("--legs"); p.add_argument("--response-file", dest="response_file"); p.add_argument("--response"); p.set_defaults(fn=cmd_log)
    p = sub.add_parser("list"); p.add_argument("--company", required=True); p.add_argument("--session", choices=["all", "current"], default="all"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("sessions"); p.add_argument("--company", required=True); p.set_defaults(fn=cmd_sessions)
    p = sub.add_parser("find"); p.add_argument("--company", required=True); p.add_argument("--remoteid", required=True); p.set_defaults(fn=cmd_find)

    a = ap.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
