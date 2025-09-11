#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weekly Tech Lab Audit
- Requires NOTION_TOKEN and NOTION_DB from .env
- WEEK_START=YYYY-MM-DD (Monday) optional, defaults to this week’s Monday
- WEEK_END  =YYYY-MM-DD optional, defaults to WEEK_START+6
Exports:
  • CSV  -> ~/Documents/TechLabAudit/exports/weekly/weekly_YYYY-MM-DD_to_YYYY-MM-DD.csv
  • HTML -> ~/Documents/TechLabAudit/exports/weekly/weekly_YYYY-MM-DD_to_YYYY-MM-DD_dashboard.html
"""

import os, sys, csv, requests, datetime
from datetime import timedelta, timezone

# ------------------ CONFIG ------------------
OUT_DIR = os.path.expanduser("~/Documents/TechLabAudit/exports/weekly")
os.makedirs(OUT_DIR, exist_ok=True)

NOTION_BASE = "https://api.notion.com/v1"
NOTION_V    = "2022-06-28"

# Notion property names
P_FIRST   = "FIRST NAME"
P_LAST    = "LAST NAME"
P_CONSOLE = "CONSOLE #"
P_IN      = "DATE OF ENTRY"
P_OUT     = "DATE OF EXIT"

# ---- Notion text helpers (robust) ----
def _first_text(arr):
    return (arr or [{}])[0].get("plain_text", "") if arr else ""

def prop_title_text(props, name):
    """Text from a Title property (array of 'title' runs)."""
    p = props.get(name) or {}
    return _first_text(p.get("title"))

def prop_rich_text(props, name):
    """Text from a Rich text property (array of 'rich_text' runs)."""
    p = props.get(name) or {}
    return _first_text(p.get("rich_text"))

def prop_select_name(props, name):
    """Name from select or multi-select; multi-select -> comma list."""
    p = props.get(name) or {}
    if p.get("type") == "select":
        sel = p.get("select") or {}
        return sel.get("name", "")
    if p.get("type") == "multi_select":
        return ", ".join([t.get("name","") for t in (p.get("multi_select") or [])])
    return ""

def prop_console_value(props, name):
    """Console can be select or rich text in your space; prefer select name."""
    return prop_select_name(props, name) or prop_rich_text(props, name)

def prop_any_text(props, name):
    """Try title, then rich_text, then select, in that order."""
    return (
        prop_title_text(props, name)
        or prop_rich_text(props, name)
        or prop_select_name(props, name)
    )
    
# ------------------ UTILS -------------------
def die(msg, code=1):
    print(f"❌ {msg}")
    sys.exit(code)

def get_env(n):
    v = os.environ.get(n, "").strip()
    return v or None

def monday_of_this_week():
    today = datetime.date.today()
    return today - timedelta(days=today.weekday())

def parse_date(s):
    return datetime.date.fromisoformat(s)

def safe_date_start(p):
    if not p: return None
    d = p.get("date")
    return d.get("start") if d else None

def parse_iso_to_local(s):
    if not s: return None
    s = s.replace("Z","+00:00")
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except Exception:
        return None

def pretty_time(s):
    dt = parse_iso_to_local(s)
    if not dt: return ""
    return dt.strftime("%-I:%M %p") if sys.platform!="win32" else dt.strftime("%#I:%M %p")

def minutes_between(a,b):
    a = parse_iso_to_local(a)
    b = parse_iso_to_local(b)
    if not a or not b: return None
    return max(0, int((b-a).total_seconds()//60))

def notion_query_database(db_id, token, filter_obj=None, page_size=100):
    url = f"{NOTION_BASE}/databases/{db_id}/query"
    headers = {"Authorization": f"Bearer {token}","Notion-Version":NOTION_V,"Content-Type":"application/json"}
    body = {"page_size": page_size}
    if filter_obj: body["filter"]=filter_obj

    while True:
        r = requests.post(url, headers=headers, json=body)
        if not r.ok: die(f"Notion error {r.status_code}: {r.text}")
        j = r.json()
        for res in j.get("results", []): yield res
        if not j.get("has_more"): break
        body["start_cursor"]=j.get("next_cursor")

# ------------------ HTML RENDER -------------------
def render_week_html(start, end, agg, day_keys):
    max_sessions = max([agg[d]["sessions"] for d in day_keys] + [1])
    max_minutes  = max([agg[d]["minutes"]  for d in day_keys] + [1])

    # sparkline: scaled bars
    spark = "".join(
        f'<rect x="{i*12}" y="{40-int(40*agg[d]["minutes"]/max_minutes)}" '
        f'width="10" height="{int(40*agg[d]["minutes"]/max_minutes)}" fill="#19b3ff" />'
        for i,d in enumerate(day_keys)
    )

    body = "\n".join(
        f"""<tr>
              <td>{d}</td>
              <td><div class="bar"><span style="width:{int(100*agg[d]['sessions']/max_sessions)}%"></span></div> {agg[d]['sessions']}</td>
              <td class="num">{agg[d]['completed']}</td>
              <td class="num">{agg[d]['open']}</td>
              <td class="num">{agg[d]['over30']}</td>
              <td><div class="bar"><span class="min" style="width:{int(100*agg[d]['minutes']/max_minutes)}%"></span></div> {agg[d]['minutes']}</td>
            </tr>"""
        for d in day_keys
    )

    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>Weekly Audit — {start} to {end}</title>
<style>
  body {{ font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin:24px; background:#0b0f14; color:#e8eef6; }}
  h1 {{ margin:0 0 6px; font-size:22px; }}
  .sub {{ color:#9fb3c8; margin:0 0 18px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ padding:10px; border-bottom:1px solid #1b2533; text-align:left; vertical-align:middle; }}
  th {{ color:#9fb3c8; font-weight:600; font-size:12px; letter-spacing:.2px; }}
  td.num {{ text-align:right; }}
  .bar {{ background:#0d1320; border:1px solid #1a2432; height:10px; border-radius:999px; overflow:hidden; display:inline-block; width:160px; margin-right:8px; vertical-align:middle; }}
  .bar>span {{ display:block; height:10px; background:linear-gradient(90deg,#19b3ff,#8b5cf6); }}
  .bar>span.min {{ background:linear-gradient(90deg,#22c55e,#16a34a); }}
  svg {{ margin-top:16px; }}
</style>
<body>
  <h1>Weekly Audit — {start} to {end}</h1>
  <div class="sub">Per-day totals (sessions, completions, opens, over-30s, minutes).</div>
  <svg width="{len(day_keys)*12}" height="50">{spark}</svg>
  <table>
    <thead><tr><th>Date</th><th>Sessions</th><th>Completed</th><th>Open</th><th>Over 30 min</th><th>Total Minutes</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</body></html>"""

# ------------------ MAIN -------------------
def main():
    token = get_env("NOTION_TOKEN")
    db_id = get_env("NOTION_DB")
    if not token or not db_id:
        die("Missing NOTION_TOKEN or NOTION_DB")

    ws = get_env("WEEK_START")
    start = parse_date(ws) if ws else monday_of_this_week()
    we = get_env("WEEK_END")
    end = parse_date(we) if we else start+timedelta(days=6)

    print(f"🗓️ Weekly audit {start} → {end}")

    filter_obj={"and":[
        {"property":P_IN,"date":{"on_or_after":start.isoformat()}},
        {"property":P_IN,"date":{"on_or_before":end.isoformat()}}
    ]}

    day_keys=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    agg={d:{"sessions":0,"completed":0,"open":0,"over30":0,"minutes":0} for d in day_keys}

    for pg in notion_query_database(db_id, token, filter_obj=filter_obj):
        props=pg.get("properties",{})
        pin=props.get(P_IN); pout=props.get(P_OUT)
        pin_iso=safe_date_start(pin); pout_iso=safe_date_start(pout)
        if not pin_iso: continue
        day=parse_iso_to_local(pin_iso).date().isoformat()
        if day not in agg: continue

        agg[day]["sessions"]+=1
        mins=minutes_between(pin_iso,pout_iso)
        if mins is None: agg[day]["open"]+=1
        else:
            agg[day]["completed"]+=1; agg[day]["minutes"]+=mins
            if mins>30: agg[day]["over30"]+=1

    # --- CSV ---
    csv_path=os.path.join(OUT_DIR,f"weekly_{start}_to_{end}.csv")
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["Date","Sessions","Completed","Open","Over 30 min","Total Minutes"])
        for d in day_keys:
            a=agg[d]; w.writerow([d,a["sessions"],a["completed"],a["open"],a["over30"],a["minutes"]])
    print(f"✅ Wrote {csv_path}")

    # --- HTML ---
    html_path=os.path.join(OUT_DIR,f"weekly_{start}_to_{end}_dashboard.html")
    html=render_week_html(start,end,agg,day_keys)
    with open(html_path,"w",encoding="utf-8") as f: f.write(html)
    print(f"✅ Wrote {html_path}")

if __name__=="__main__":
    main()