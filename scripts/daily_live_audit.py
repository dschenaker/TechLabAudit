#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Daily Tech Lab audit with styled CSV + HTML output.
- Requires NOTION_TOKEN, NOTION_DB environment variables
- AUDIT_DATE=YYYY-MM-DD (defaults to today if not set)
- Exports:
    • CSV  -> ~/Documents/TechLabAudit/exports/daily/daily_YYYY-MM-DD.csv
    • HTML -> ~/Documents/TechLabAudit/exports/daily/daily_YYYY-MM-DD_dashboard.html
"""

import os, sys, csv, requests, datetime
from datetime import timezone

# ----------- Notion property names (must match your DB headers) -----------
P_FIRST   = "FIRST NAME"    # Title
P_LAST    = "LAST NAME"     # Rich text
P_CONSOLE = "CONSOLE #"
P_IN      = "DATE OF ENTRY"
P_OUT     = "DATE OF EXIT"

NOTION_BASE = "https://api.notion.com/v1"
NOTION_V    = "2022-06-28"

# ----------- Export directories -----------
OUT_BASE = os.path.join(os.path.expanduser("~"), "Documents", "TechLabAudit", "exports")
OUT_DIR  = os.path.join(OUT_BASE, "daily")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------- Utils -----------
def die(msg, code=1):
    print(f"❌ {msg}")
    sys.exit(code)

def get_env(n): 
    v = os.environ.get(n, "").strip()
    return v or None

def today_local_date():
    return datetime.datetime.now().date()

def safe_date_start(p):
    if not p: return None
    d = p.get("date")
    return d.get("start") if d else None

def parse_iso_to_local(iso_s):
    if not iso_s: return None
    s = iso_s.replace("Z","+00:00")
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except Exception:
        return None

def pretty_time(iso_s):
    dt = parse_iso_to_local(iso_s)
    if not dt: return ""
    return dt.strftime("%-I:%M %p") if sys.platform!="win32" else dt.strftime("%#I:%M %p")

def minutes_between(a_iso,b_iso):
    a = parse_iso_to_local(a_iso)
    b = parse_iso_to_local(b_iso)
    if not a or not b: return None
    m = int((b-a).total_seconds()//60)
    return max(m,0)

# ---- Notion text helpers (robust) ----
def _first_text(arr):
    return (arr or [{}])[0].get("plain_text", "") if arr else ""

def prop_title_text(props, name):
    p = props.get(name) or {}
    return _first_text(p.get("title"))

def prop_rich_text(props, name):
    p = props.get(name) or {}
    return _first_text(p.get("rich_text"))

def prop_select_name(props, name):
    p = props.get(name) or {}
    if p.get("type") == "select":
        sel = p.get("select") or {}
        return sel.get("name", "")
    if p.get("type") == "multi_select":
        return ", ".join([t.get("name","") for t in (p.get("multi_select") or [])])
    return ""

def prop_console_value(props, name):
    return prop_select_name(props, name) or prop_rich_text(props, name)

def prop_any_text(props, name):
    return (
        prop_title_text(props, name)
        or prop_rich_text(props, name)
        or prop_select_name(props, name)
    )

# ----------- Notion API -----------
def notion_query_database(db_id, token, filter_obj=None, page_size=100):
    url = f"{NOTION_BASE}/databases/{db_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_V, "Content-Type":"application/json"}
    body = {"page_size": page_size}
    if filter_obj: body["filter"] = filter_obj

    while True:
        r = requests.post(url, headers=headers, json=body)
        if not r.ok: die(f"Notion error {r.status_code}: {r.text}")
        j = r.json()
        for res in j.get("results", []):
            yield res
        if not j.get("has_more"): break
        body["start_cursor"]=j.get("next_cursor")

# ----------- Main -----------
def main():
    token = get_env("NOTION_TOKEN")
    db_id = get_env("NOTION_DB")
    if not token or not db_id:
        die("Missing NOTION_TOKEN or NOTION_DB")

    audit_date = get_env("AUDIT_DATE")
    if audit_date:
        audit_date = datetime.date.fromisoformat(audit_date)
    else:
        audit_date = today_local_date()

    print(f"📅 Daily audit for {audit_date}")

    filter_obj = {"property": P_IN, "date": {"equals": audit_date.isoformat()}}

    pages = notion_query_database(db_id, token, filter_obj=filter_obj)

    clean_rows = []
    open_sessions = []
    over_30 = []

    for pg in pages:
        props = pg.get("properties", {})

        first   = prop_title_text(props, P_FIRST)
        last    = prop_any_text(props, P_LAST)
        console = prop_console_value(props, P_CONSOLE)

        pin  = props.get(P_IN)
        pout = props.get(P_OUT)

        time_in_iso  = safe_date_start(pin)
        time_out_iso = safe_date_start(pout)

        if not time_in_iso: 
            continue

        minutes = minutes_between(time_in_iso, time_out_iso)

        if minutes is None:
            open_sessions.append({"First Name": first, "Last Name": last})
        else:
            if minutes > 30:
                over_30.append((f"{first} {last}", minutes))

        clean_rows.append({
            "First Name": first,
            "Last Name": last,
            "Console #": console,
            "Time In":  pretty_time(time_in_iso),
            "Time Out": pretty_time(time_out_iso),
            "Minutes":  "" if minutes is None else minutes,
        })

    # --- Write CSV ---
    csv_path = os.path.join(OUT_DIR, f"daily_{audit_date}.csv")
    headers = ["First Name","Last Name","Console #","Time In","Time Out","Minutes"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(clean_rows)

    print(f"✅ Wrote {csv_path} with {len(clean_rows)} rows")

    # --- Write HTML ---
    def esc(s): return (str(s) if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    rows_html = "\n".join(
        f"<tr><td>{esc(r['First Name'])}</td><td>{esc(r['Last Name'])}</td><td>{esc(r['Console #'])}</td>"
        f"<td>{esc(r['Time In'])}</td><td>{esc(r['Time Out'])}</td><td class='num'>{esc(r['Minutes'])}</td></tr>"
        for r in clean_rows
    )

    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Daily Audit — {audit_date}</title>
<style>
  body {{ font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin:24px; background:#0b0f14; color:#e8eef6; }}
  h1 {{ margin:0 0 6px; font-size:22px; }}
  .sub {{ color:#9fb3c8; margin:0 0 18px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ padding:10px; border-bottom:1px solid #1b2533; text-align:left; vertical-align:middle; }}
  th {{ color:#9fb3c8; font-weight:600; font-size:12px; letter-spacing:.2px; }}
  td.num {{ text-align:right; }}
</style>
<body>
  <h1>Daily Audit — {audit_date}</h1>
  <div class="sub">Sessions: {len(clean_rows)} | Open sessions: {len(open_sessions)} | Over 30 min: {len(over_30)}</div>
  <table>
    <thead><tr><th>First Name</th><th>Last Name</th><th>Console #</th><th>Time In</th><th>Time Out</th><th>Minutes</th></tr></thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>"""

    html_path = os.path.join(OUT_DIR, f"daily_{audit_date}_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Wrote {html_path}")

if __name__ == "__main__":
    main()