#!/usr/bin/env python3
"""Update data/data.json from TrackMaster Harness Virtual Stable emails.
 
Reads Gmail over IMAP in READ-ONLY mode (never marks, moves or deletes mail),
keeps only horses trained by Scott Betts, then:
  * adds new results / scratches to each horse's starts (newest first),
  * updates a start whose finish changed,
  * adds a new horse (with sire/dam) in alphabetical position if needed,
  * rebuilds "upcoming" from Entry / Race Day emails dated today (ET) or later.
 
Usage:
  python3 -I trackmaster_update.py data/data.json            # live, via IMAP
  python3 -I trackmaster_update.py data/data.json --eml DIR   # offline test on .eml/.html files
 
Environment (live mode): GMAIL_USER, GMAIL_APP_PASSWORD.
Optional: LOOKBACK_DAYS (default 12), SUMMARY_FILE (one-line summary for the commit message).
"""
import datetime as dt
import email
import email.policy
import html
import imaplib
import json
import os
import re
import sys
from zoneinfo import ZoneInfo
 
TRAINER_PREFIX = "BETTS, SCOTT"
SENDER = "hvs@trackmaster.com"
ET = ZoneInfo("America/New_York")
 
 
# ---------------------------------------------------------------- parsing ---
 
def html_to_text(fragment):
    """Turn a TrackMaster HTML fragment into plain text lines."""
    t = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", fragment)
    t = re.sub(r"(?i)<\s*(br|p|/p|div|/div|hr)\b[^>]*>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)
 
 
def split_blocks(body_html):
    """One email can hold several horses separated by <hr>."""
    m = re.search(r'(?is)<div class="messageBody">(.*)', body_html)
    body = m.group(1) if m else body_html
    return re.split(r"(?i)<hr\b[^>]*>", body)
 
 
def mdy(s):
    m, d, y = s.split("/")
    y = int(y)
    if y < 100:
        y += 2000
    return f"{y:04d}-{int(m):02d}-{int(d):02d}"
 
 
def field(text, label):
    m = re.search(label + r"\s*:\s*(.*)", text)
    return m.group(1).strip() if m else None
 
 
def parse_result_block(block_html):
    text = html_to_text(block_html)
    m = re.search(r"^(.+?)\s+was entered to race on (\d{1,2}/\d{1,2}/\d{2,4}) at (.+?), Race #\s*(\d+)",
                  text, re.M)
    if not m:
        return None
    name, date, track, race = m.group(1).strip().upper(), mdy(m.group(2)), m.group(3).strip(), int(m.group(4))
    sd = re.search(r"Sire:\s*(.*?)\s*Dam:\s*(.*)", text)
    dt_line = re.search(r"Driver:\s*(.*?)\s*Trainer:\s*(.*)", text)
    if not dt_line:
        return None
    driver, trainer = dt_line.group(1).strip(), dt_line.group(2).strip()
    chart = re.search(r'href="([^"]*hchxml2html[^"]*)"', block_html, re.I)
    finish = field(text, r"Finishing Position") or ""
    odds = field(text, r"Odds to \$1")
    if finish.lower().startswith("scratch"):
        finish, odds, driver = "Scratched", None, None
    else:
        if odds and odds.lower().startswith("not applicable"):
            odds = None
        if driver.lower().startswith("not applicable"):
            driver = None
    return {
        "kind": "result", "name": name, "trainer": trainer,
        "sire": sd.group(1).strip() if sd else "", "dam": sd.group(2).strip() if sd else "",
        "start": {
            "date": date, "track": track, "race": race, "finish": finish,
            "odds": odds, "driver": driver,
            "time": field(text, r"Race Time") or "",
            "chartUrl": html.unescape(chart.group(1)) if chart else None,
        },
    }
 
 
def parse_entry_block(block_html):
    text = html_to_text(block_html)
    m = re.search(r"^(.+?)\s+is entered on (\d{1,2}/\d{1,2}/\d{2,4}) at (.+)$", text, re.M)
    race = re.search(r"Race #\s*:\s*(\d+)", text)
    trainer = re.search(r"Trainer\s*:\s*(.*)", text)
    if not (m and race and trainer):
        return None
    sd = re.search(r"Sire:\s*(.*?)\s*Dam:\s*(.*)", text)
    return {
        "kind": "entry", "name": m.group(1).strip().upper(), "trainer": trainer.group(1).strip(),
        "sire": sd.group(1).strip() if sd else "", "dam": sd.group(2).strip() if sd else "",
        "date": mdy(m.group(2)), "track": m.group(3).strip(), "race": int(race.group(1)),
    }
 
 
def parse_email_html(body_html):
    head = html_to_text(body_html[:4000]).upper()
    if "RESULT NOTIFICATION" in head:
        parser = parse_result_block
    elif "ENTRY NOTIFICATION" in head or "RACE DAY NOTIFICATION" in head:
        parser = parse_entry_block
    else:
        return []  # password requests, newsletters, etc.
    out = []
    for block in split_blocks(body_html):
        item = parser(block)
        if item:
            out.append(item)
    return out
 
 
def html_of_message(raw_bytes):
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    part = msg.get_body(preferencelist=("html",))
    if part is None:
        part = msg.get_body(preferencelist=("plain",))
        if part is None:
            return ""
        return html.escape(part.get_content()).replace("\n", "<br>")
    return part.get_content()
 
 
# ------------------------------------------------------------ fetching -----
 
def fetch_live(lookback_days):
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(user, pw)
    try:
        # All Mail so archived/filtered messages count too; readonly=True means
        # nothing in the mailbox is ever changed.
        all_mail = '"[Gmail]/All Mail"'
        typ, boxes = imap.list()
        for b in boxes or []:
            line = b.decode(errors="replace") if isinstance(b, bytes) else str(b)
            if "\\All" in line:  # Gmail's All Mail folder, whatever its local name
                all_mail = line[line.rfind(' "') + 1:] if line.endswith('"') else line.split()[-1]
                break
        typ, _ = imap.select(all_mail, readonly=True)
        if typ != "OK":
            typ, _ = imap.select("INBOX", readonly=True)
            if typ != "OK":
                raise RuntimeError("could not open mailbox")
        query = f"from:{SENDER} newer_than:{lookback_days}d"
        typ, data = imap.search(None, "X-GM-RAW", f'"{query}"')
        if typ != "OK":
            raise RuntimeError(f"IMAP search failed: {typ}")
        ids = data[0].split()
        bodies = []
        for i in ids:
            typ, msg_data = imap.fetch(i, "(BODY.PEEK[])")  # PEEK: never sets \Seen
            if typ == "OK" and msg_data and isinstance(msg_data[0], tuple):
                bodies.append(html_of_message(msg_data[0][1]))
        return bodies
    finally:
        try:
            imap.logout()
        except Exception:
            pass
 
 
def fetch_offline(directory):
    bodies = []
    for fn in sorted(os.listdir(directory)):
        p = os.path.join(directory, fn)
        raw = open(p, "rb").read()
        bodies.append(html_of_message(raw) if fn.endswith(".eml") else raw.decode("utf-8"))
    return bodies
 
 
# ------------------------------------------------------------- merging -----
 
def is_betts(trainer):
    return trainer.upper().startswith(TRAINER_PREFIX)
 
 
def merge(data, items, today):
    horses = data["horses"]
    by_name = {h["name"]: h for h in horses}
    notes = []
 
    def get_horse(item):
        h = by_name.get(item["name"])
        if h is None:
            h = {"name": item["name"], "sire": item["sire"], "dam": item["dam"], "starts": []}
            names = [x["name"] for x in horses]
            pos = next((i for i, n in enumerate(names) if n > item["name"]), len(horses))
            horses.insert(pos, h)
            by_name[item["name"]] = h
            notes.append(f"new horse {item['name'].title()}")
        return h
 
    for it in items:
        if it["kind"] != "result" or not is_betts(it["trainer"]):
            continue
        h = get_horse(it)
        s = it["start"]
        existing = next((x for x in h["starts"] if x["date"] == s["date"] and x["race"] == s["race"]), None)
        label = f"{it['name'].title()} {s['finish']} at {s['track']} ({int(s['date'][5:7])}/{int(s['date'][8:])})"
        if existing is None:
            h["starts"].append(s)
            notes.append(label)
        elif existing.get("finish") != s["finish"]:
            existing.clear()
            existing.update(s)
            notes.append(label + " (updated)")
        h["starts"].sort(key=lambda x: x["date"], reverse=True)  # stable: keeps same-day order
 
    upcoming, seen = [], set()
    for it in items:
        if it["kind"] != "entry" or not is_betts(it["trainer"]) or it["date"] < today:
            continue
        key = (it["name"], it["date"], it["race"])
        if key in seen:
            continue
        seen.add(key)
        upcoming.append({"date": it["date"], "horse": it["name"], "track": it["track"], "race": it["race"]})
    upcoming.sort(key=lambda u: (u["date"], u["race"], u["horse"]))
    if upcoming != data.get("upcoming", []):
        old = {(u["horse"], u["date"], u["race"]) for u in data.get("upcoming", [])}
        for u in upcoming:
            if (u["horse"], u["date"], u["race"]) not in old:
                notes.append(f"{u['horse'].title()} entered at {u['track']} {int(u['date'][5:7])}/{int(u['date'][8:])}")
        if not upcoming:
            notes.append("cleared past entries")
    data["upcoming"] = upcoming
    return notes
 
 
# ---------------------------------------------------------------- main -----
 
def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    path = argv[1]
    raw = open(path, encoding="utf-8").read()
    data = json.loads(raw)  # fails loudly if unreadable; never start from empty data
    if not isinstance(data, dict) or not data.get("horses"):
        sys.exit("data.json has no horses; refusing to continue")
 
    lookback = int(os.environ.get("LOOKBACK_DAYS", "12"))
    if "--eml" in argv:
        bodies = fetch_offline(argv[argv.index("--eml") + 1])
    else:
        bodies = fetch_live(lookback)
 
    items = []
    for b in bodies:
        items.extend(parse_email_html(b))
    print(f"read {len(bodies)} TrackMaster emails, {len(items)} horse notices "
          f"({sum(is_betts(i['trainer']) for i in items)} for the Betts barn)")
 
    today = os.environ.get("TODAY") or dt.datetime.now(ET).date().isoformat()
    notes = merge(data, items, today)
 
    new_raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if new_raw != raw.rstrip("\n"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_raw)
    summary = "; ".join(notes) if notes else "no new results"
    print("summary:", summary)
    if os.environ.get("SUMMARY_FILE"):
        with open(os.environ["SUMMARY_FILE"], "w", encoding="utf-8") as f:
            f.write(summary[:200])
 
 
if __name__ == "__main__":
    main(sys.argv)
 
