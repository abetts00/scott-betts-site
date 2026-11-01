#!/usr/bin/env python3
"""Scott Betts Racing static site generator.

Usage: python3 build.py <data.json> <config.json> <output_dir>
Pages: index, horses, racing (entries + results + replays), about, memoriam;
redirects: entries, results, replays -> racing sections, phoenix -> memoriam
"""
import html
import json
import re
import sys
from urllib.parse import quote
from datetime import date, datetime
from pathlib import Path

def esc(v):
    return html.escape("" if v is None else str(v))

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def fmt_date(s):
    d = parse_date(s)
    return d.strftime("%b %-d, %Y") if d else esc(s)

def final_time(t):
    if not t:
        return None
    parts = [p.strip() for p in str(t).split("-")]
    return parts[-1] if parts and parts[-1] else None

def secs(t):
    m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", t or "")
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None

def place(finish):
    m = re.match(r"^(\d+)", finish or "")
    return int(m.group(1)) if m else None

def is_scratch(finish):
    return "scratch" in (finish or "").lower()

def horse_stats(h):
    starts = [s for s in h.get("starts", []) if not is_scratch(s.get("finish"))]
    w = sum(1 for s in starts if place(s.get("finish")) == 1)
    p = sum(1 for s in starts if place(s.get("finish")) == 2)
    sh = sum(1 for s in starts if place(s.get("finish")) == 3)
    best = None
    for s in starts:
        ft = final_time(s.get("time"))
        if secs(ft) is not None and (best is None or secs(ft) < secs(best)):
            best = ft
    return {"starts": len(starts), "w": w, "p": p, "s": sh, "best": best}

ICONS = {
    "facebook": '<svg viewBox="0 0 24 24"><path d="M24 12.07C24 5.45 18.63.07 12 .07S0 5.45 0 12.07c0 5.99 4.39 10.95 10.13 11.85v-8.39H7.08v-3.47h3.05V9.43c0-3.01 1.79-4.67 4.53-4.67 1.31 0 2.69.24 2.69.24v2.95h-1.52c-1.49 0-1.96.93-1.96 1.87v2.25h3.33l-.53 3.47h-2.8v8.39C19.61 23.03 24 18.06 24 12.07z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24"><path d="M12 2.2c3.2 0 3.6 0 4.8.1 3.3.1 4.8 1.7 4.9 4.9.1 1.3.1 1.6.1 4.8s0 3.6-.1 4.8c-.1 3.2-1.7 4.8-4.9 4.9-1.3.1-1.6.1-4.8.1s-3.6 0-4.8-.1c-3.3-.1-4.8-1.7-4.9-4.9C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.8C2.4 3.9 4 2.4 7.2 2.3 8.4 2.2 8.8 2.2 12 2.2zM12 0C8.7 0 8.3 0 7.1.1 2.7.3.3 2.7.1 7.1 0 8.3 0 8.7 0 12s0 3.7.1 4.9c.2 4.4 2.6 6.8 7 7 1.2.1 1.6.1 4.9.1s3.7 0 4.9-.1c4.4-.2 6.8-2.6 7-7 .1-1.2.1-1.6.1-4.9s0-3.7-.1-4.9c-.2-4.4-2.6-6.8-7-7C15.7 0 15.3 0 12 0zm0 5.8a6.2 6.2 0 1 0 0 12.4 6.2 6.2 0 0 0 0-12.4zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.4-11.8a1.4 1.4 0 1 0 0 2.9 1.4 1.4 0 0 0 0-2.9z"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.6 15.6V8.4l6.2 3.6z"/></svg>',
    "x": '<svg viewBox="0 0 24 24"><path d="M18.2 2.3h3.3l-7.2 8.3 8.5 11.2h-6.7l-5.2-6.8-6 6.8H1.6l7.7-8.8L1.2 2.3H8l4.7 6.2zm-1.2 17.5h1.8L7 4.1H5.1z"/></svg>',
    "tiktok": '<svg viewBox="0 0 24 24"><path d="M16.6 2h-3.2v13.2a2.9 2.9 0 1 1-2.9-2.9c.3 0 .6 0 .8.1V9a6.1 6.1 0 1 0 5.3 6V8.6a7.4 7.4 0 0 0 4.3 1.4V6.8a4.3 4.3 0 0 1-4.3-4.8z"/></svg>',
}

def socials_html(cfg):
    s = cfg.get("socials", {})
    out = []
    for key in ("facebook", "instagram", "youtube", "x", "tiktok"):
        url = (s.get(key) or "").strip()
        if url:
            out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener" aria-label="{key}">{ICONS[key]}</a>')
    return f'<div class="soc">{"".join(out)}</div>' if out else ""

def brand_html(cfg):
    logo = (cfg.get("logo") or "").strip()
    if logo:
        return f'<a class="brand" href="index.html"><img src="{esc(logo)}" alt="{esc(cfg["name"])}"></a>'
    first, _, rest = cfg.get("wordmark", "Scott Betts Racing").partition(" ")
    return f'<a class="brand" href="index.html">{esc(first)}&nbsp;<b>{esc(rest)}</b></a>'

NAV = [
    ("index.html", "Home", "home"),
    ("horses.html", "The Horses", "horses"),
    ("racing.html", "Race Day", "racing"),
    ("owners.html", "Become an Owner", "owners"),
    ("memoriam.html", "In Memoriam", "memoriam"),
    ("about.html", "Meet Scott", "about"),
]

def page(cfg, title, body, active, desc="", extra_head=""):
    links = "".join(
        f'<a href="{h}" class="{"on" if k == active else ""}">{lbl}</a>' for h, lbl, k in NAV
    )
    soc = socials_html(cfg)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or cfg['tagline'])}">
<meta name="theme-color" content="#08090b">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">{extra_head}
</head><body>
<header class="site"><div class="wrap">{brand_html(cfg)}<nav>{links}</nav>{soc}</div></header>
{body}
<footer><div class="wrap">{brand_html(cfg)}<div>&copy; {date.today().year} {esc(cfg['name'])}. Race data courtesy of TrackMaster. Updated {esc(cfg.get('updated',''))}.</div>{soc}</div></footer>
</body></html>"""

def results_table(rows, limit=None):
    if limit:
        rows = rows[:limit]
    if not rows:
        return '<p class="note">No race results to show yet.</p>'
    out = ['<div class="scroll"><table><thead><tr><th>Date</th><th>Horse</th><th>Track</th><th>Race</th><th>Finish</th><th>Time</th><th>Driver</th><th></th></tr></thead><tbody>']
    for r in rows:
        p = place(r.get("finish"))
        cls = "win" if p == 1 else ""
        pill = "w" if p == 1 else ("x" if is_scratch(r.get("finish")) else "")
        chart = (
            f'<a href="{esc(r["chartUrl"])}" target="_blank" rel="noopener">Chart</a>'
            if r.get("chartUrl")
            else ""
        )
        t = "" if is_scratch(r.get("finish")) else (final_time(r.get("time")) or "")
        out.append(
            f'<tr class="{cls}"><td>{fmt_date(r["date"])}</td><td><b>{esc(r["horse"].title())}</b></td>'
            f'<td>{esc(r.get("track"))}</td><td>{esc(r.get("race"))}</td>'
            f'<td><span class="pill {pill}">{esc(r.get("finish"))}</span></td>'
            f'<td>{esc(t)}</td><td>{esc(r.get("driver") or "")}</td><td>{chart}</td></tr>'
        )
    out.append("</tbody></table></div>")
    return "".join(out)

def upcoming_block(up):
    if not up:
        return '<div class="card"><p class="note" style="margin:0">No entries posted right now. Check back soon.</p></div>'
    rows = "".join(
        f'<tr><td>{fmt_date(u["date"])}</td><td><b>{esc(u["horse"].title())}</b></td><td>{esc(u.get("track"))}</td><td>{esc(u.get("race") or "")}</td></tr>'
        for u in up
    )
    return f'<div class="scroll"><table style="min-width:0"><thead><tr><th>Date</th><th>Horse</th><th>Track</th><th>Race</th></tr></thead><tbody>{rows}</tbody></table></div>'

def story_html(cfg):
    paras = cfg.get("story", [])
    return "".join(f"<p>{esc(p)}</p>" for p in paras)

def photo_html(cfg):
    p = (cfg.get("scottPhoto") or "").strip()
    if p:
        return f'<div class="photo"><img src="{esc(p)}" alt="Scott Betts"></div>'
    return '<div class="photo">SB</div>'

def share_pct(cfg, name):
    """Percent of a horse available for fractional purchase, or None if not listed."""
    av = {k.upper(): v for k, v in cfg.get("ownership", {}).get("available", {}).items()}
    v = av.get(name.upper())
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, v))

def pct_txt(v):
    return f"{v:g}%"

def media_html(cfg, name):
    m = {k.upper(): v for k, v in cfg.get("horseMedia", {}).items()}.get(name.upper())
    pct = share_pct(cfg, name)
    st = "width:100%;height:auto;max-height:420px;object-fit:cover;display:block;border-radius:8px;background:#000"
    if m and m.get("video"):
        poster = f' poster="{esc(m["photo"])}"' if m.get("photo") else ""
        inner = f'<video controls playsinline preload="metadata"{poster} src="{esc(m["video"])}" style="{st}"></video>'
    elif m and m.get("photo"):
        inner = f'<img src="{esc(m["photo"])}" alt="{esc(name.title())}" loading="lazy" style="{st}">'
    elif pct is not None:
        initials = "".join(w[0] for w in name.split()[:3] if w[:1].isalpha()).upper()
        inner = f'<div class="sf-ph">{esc(initials)}</div>'
    else:
        return ""
    if pct is None:
        return f'<div style="margin-bottom:14px">{inner}</div>'
    # Ring drawn around the photo: the red part of the border = share available.
    if pct >= 100:
        label = "100% available"
    elif pct <= 0:
        label = "Fully owned"
    else:
        label = f"{pct_txt(pct)} available"
    cls = " sold" if pct <= 0 else ""
    return (
        f'<div class="sf{cls}" style="--p:{pct:g}" title="{esc(label)} for fractional ownership">'
        f'<svg aria-hidden="true"><rect class="sf-track" pathLength="100"/><rect class="sf-fill" pathLength="100"/></svg>'
        f'{inner}<a class="sf-tag" href="owners.html?horse={quote(name.title())}#inquire">{esc(label)}</a></div>'
    )

def main():
    data_p, cfg_p, out_p = map(Path, sys.argv[1:4])
    data = json.loads(data_p.read_text())
    cfg = json.loads(cfg_p.read_text())
    cfg.setdefault("updated", date.today().strftime("%b %-d, %Y"))
    out_p.mkdir(parents=True, exist_ok=True)

    horses = data.get("horses", [])
    former = {n.upper() for n in cfg.get("formerHorses", [])}
    window = int(cfg.get("currentWithinDays", 90))
    today = date.today()
    pending = [n for n in cfg.get("pendingHorses", [])]
    pending_up = {n.upper() for n in pending}
    current = []
    for h in horses:
        if h["name"].upper() in former or not h.get("starts"):
            continue
        last = parse_date(h["starts"][0]["date"])
        if (last and (today - last).days <= window) or h["name"].upper() in pending_up:
            current.append(h)
    horses = current
    have = {h["name"].upper() for h in horses}
    pending = [n for n in pending if n.upper() not in have]
    for h in horses:
        for s in h["starts"]:
            u = s.get("chartUrl")
            if u and u.count("hchxml2html.cgi?") > 1:
                s["chartUrl"] = u[u.rfind("http://www.trackmaster.com/cgi-bin/hchxml2html.cgi?"):]
            d = s.get("driver")
            if d and "," in d:
                last_n, first_n = [x.strip() for x in d.split(",", 1)]
                s["driver"] = f"{first_n} {last_n}"
    all_rows = []
    for h in horses:
        for s in h.get("starts", []):
            all_rows.append({**s, "horse": h["name"]})
    all_rows.sort(key=lambda r: r["date"], reverse=True)
    upcoming = sorted(data.get("upcoming", []), key=lambda u: u["date"])

    wins = [r for r in all_rows if place(r.get("finish")) == 1]
    raced = [r for r in all_rows if not is_scratch(r.get("finish"))]
    win_pct = round(100 * len(wins) / len(raced)) if raced else 0
    n_horses = len(horses) + len(pending)

    contact = ""
    c = cfg.get("contact", {})
    lines = []
    if c.get("phone"):
        lines.append(f'Phone: <a href="tel:{esc(c["phone"])}">{esc(c["phone"])}</a>')
    if c.get("email"):
        lines.append(f'Email: <a href="mailto:{esc(c["email"])}">{esc(c["email"])}</a>')
    if c.get("location"):
        lines.append(f'Barn: {esc(c["location"])}')
    if lines:
        contact = (
            '<section class="alt"><div class="wrap"><div class="eyebrow">Get in the winner\'s circle</div><h2>Owners &amp; Inquiries</h2>'
            '<p class="sub">Interested in owning a share of a racehorse, or sending us a horse to train?</p>'
            f'<div class="card">{"<br>".join(lines)}<p style="margin:16px 0 0"><a class="btn" href="owners.html">How ownership works</a></p></div></div></section>'
        )

    # ---------- home ----------
    ss = cfg.get("seasonStats")
    if ss:
        tiles = [
            (ss["starts"], f'Starts in {ss["year"]}'),
            (f'{ss["wins"]}-{ss["seconds"]}-{ss["thirds"]}', "Wins - Places - Shows"),
            (ss["earnings"], "Earnings"),
            (ss["rating"], "Rating"),
        ]
    else:
        tiles = [(len(wins), "Wins this season"), (len(raced), "Starts"), (f"{win_pct}%", "Win rate"), (n_horses, "Horses in the barn")]
    stats_html = '<div class="stats"><div class="wrap">' + "".join(f'<div class="stat"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in tiles)
    home = f"""
<div class="hero"><div class="wrap">
<div class="badge">2018 Meadows Horse of the Year &middot; Phoenix Warrior N</div>
<h1>Scott Betts<br><span class="grad">Racing</span></h1>
<p class="tag">{esc(cfg['tagline'])}. Standardbreds trained at The Meadows and raced at Northfield Park and beyond.</p>
<a class="btn" href="horses.html">Meet the Horses</a><a class="btn alt" href="racing.html#replays">Watch Replays</a>
</div></div>
{stats_html}
</div></div>
<section><div class="wrap cols">
<div><div class="eyebrow">Live from the track</div><h2>Recent Results</h2><p class="sub">Updated automatically every morning from TrackMaster race charts.</p>
{results_table(all_rows, 8)}
<p><a href="racing.html#results">See all results &rarr;</a></p></div>
<div><div class="eyebrow">Coming up</div><h2>Up Next</h2><p class="sub">Entries for the coming days.</p>{upcoming_block(upcoming)}<p><a href="racing.html#entries">All entries &rarr;</a></p></div>
</div></section>
<section class="alt"><div class="wrap about">
{photo_html(cfg)}
<div class="story"><div class="eyebrow">The trainer</div><h2>Meet Scott</h2>
{story_html(cfg).split("</p>")[0] + "</p>" if cfg.get("story") else ""}
<a class="btn" href="about.html">Read Scott's story</a></div>
</div></section>
{contact}"""
    (out_p / "index.html").write_text(page(cfg, cfg["name"], home, "home"))

    # ---------- horses ----------
    cards = []
    for h in sorted(horses, key=lambda h: h["name"]):
        st = horse_stats(h)
        last = next((x for x in h.get("starts", []) if not is_scratch(x.get("finish"))), None)
        last_html = ""
        if last:
            lt = final_time(last.get("time"))
            last_html = (
                f'<div class="last"><b>Last start:</b> {fmt_date(last["date"])} at {esc(last.get("track"))}, '
                f'{esc(last.get("finish"))}' + (f' in {esc(lt)}' if lt else "") + "</div>"
            )
        cards.append(
            f'<div class="card horse">{media_html(cfg, h["name"])}<h3>{esc(h["name"].title())}</h3>'
            f'<div class="pedi">{esc((h.get("sire") or "").title())} &times; {esc((h.get("dam") or "").title())}</div>'
            f'<div class="rec"><div><b>{st["starts"]}</b><span>Starts</span></div><div><b>{st["w"]}</b><span>Wins</span></div>'
            f'<div><b>{st["p"]}</b><span>2nd</span></div><div><b>{st["s"]}</b><span>3rd</span></div>'
            f'<div><b>{esc(st["best"] or "-")}</b><span>Best mile</span></div></div>{last_html}</div>'
        )
    for n in pending:
        cards.append(
            f'<div class="card horse">{media_html(cfg, n)}<span class="new">New to the barn</span><h3>{esc(n.title())}</h3>'
            '<div class="pedi">Race record loading soon</div>'
            '<div class="last" style="border:0;padding-top:0;margin-top:0">First starts will appear here automatically as soon as results post.</div></div>'
        )
    own_cfg = cfg.get("ownership", {})
    listed = {n: share_pct(cfg, n) for n in own_cfg.get("available", {}) if share_pct(cfg, n) is not None}
    legend = ""
    if any(v > 0 for v in listed.values()):
        legend = (
            '<div class="sf-legend"><span class="sf-key"></span><div><b>Red ring = share available to own.</b> '
            'The more of the border that is lit, the more of that horse is open for fractional purchase. '
            f'<a href="owners.html">How ownership works &rarr;</a></div></div>'
        )
    horses_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">The barn</div><h1>The <span class="grad">Horses</span></h1></div></div>
<section><div class="wrap"><p class="sub">Current members of the stable. Records reflect starts this season.</p>{legend}
<div class="grid">{"".join(cards) or '<p class="note">Roster coming soon.</p>'}</div></div></section>{contact}"""
    (out_p / "horses.html").write_text(page(cfg, "The Horses | " + cfg["name"], horses_body, "horses"))

    # ---------- racing (entries + results + replays on one page) ----------
    win_cards = []
    for r in wins[:12]:
        t = final_time(r.get("time")) or ""
        link = (
            f'<a class="play" href="{esc(r["chartUrl"])}" target="_blank" rel="noopener">&#9654; Chart &amp; replay</a>'
            if r.get("chartUrl")
            else ""
        )
        win_cards.append(
            f'<div class="card win-card"><h3>{esc(r["horse"].title())}</h3>'
            f'<div class="m">{fmt_date(r["date"])} &middot; {esc(r.get("track"))} &middot; Race {esc(r.get("race"))}'
            f'{" &middot; " + esc(r.get("driver")) if r.get("driver") else ""}</div>'
            f'<div class="t">Won in {esc(t)}</div>{link}</div>'
        )
    vids = cfg.get("videos", [])
    vid_html = ""
    if vids:
        items = "".join(
            f'<div><iframe class="vid" loading="lazy" src="https://www.youtube.com/embed/{esc(v["youtube"])}" '
            f'title="{esc(v.get("title",""))}" allowfullscreen></iframe><p class="note">{esc(v.get("title",""))}</p></div>'
            for v in vids
        )
        vid_html = f'<section id="videos"><div class="wrap"><div class="eyebrow">Featured</div><h2>Race Videos</h2><div class="vids">{items}</div></div></section>'
    jump_css = ('<style>.jump{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}'
                '.jump a{border:1.5px solid var(--line);color:var(--text);text-decoration:none;padding:9px 16px;border-radius:999px;'
                'font:700 .72rem/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase}'
                '.jump a:hover{border-color:var(--flame2);color:var(--flame2)}'
                'section[id]{scroll-margin-top:90px}</style>')
    jumps = [("entries", "Entries"), ("replays", "Replays")] + ([("videos", "Videos")] if vids else []) + [("results", "Results")]
    racing_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">Entries &middot; Replays &middot; Results</div><h1>Race <span class="grad">Day</span></h1>
<div class="jump">{"".join(f'<a href="#{k}">{v}</a>' for k, v in jumps)}</div></div></div>
<section id="entries"><div class="wrap"><div class="eyebrow">Coming up</div><h2>Upcoming Entries</h2>
<p class="sub">Horses entered to race in the coming days. Updated daily from TrackMaster.</p>
{upcoming_block(upcoming)}</div></section>
<section id="replays" class="alt"><div class="wrap"><div class="eyebrow">Relive it</div><h2>Win Circle</h2>
<p class="sub">Every winner this season. Each button opens the TrackMaster chart, which has the video replay.</p>
<div class="wins">{"".join(win_cards) or '<p class="note">No wins yet this season.</p>'}</div></div></section>
{vid_html}
<section id="results"{' class="alt"' if vids else ''}><div class="wrap"><div class="eyebrow">Every start, every week</div><h2>Race Results</h2>
<p class="sub">{len(raced)} starts, {len(wins)} wins this season. Winners are highlighted. Click Chart for the full TrackMaster race chart and replay.</p>
{results_table(all_rows)}</div></section>{contact}"""
    (out_p / "racing.html").write_text(page(cfg, "Race Day | " + cfg["name"], racing_body, "racing",
        "Upcoming entries, race results and replays for the Scott Betts stable.", jump_css))
    for old, anchor, label in (("entries", "entries", "Entries"), ("results", "results", "Results"), ("replays", "replays", "Replays")):
        (out_p / f"{old}.html").write_text(
            f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=racing.html#{anchor}">'
            f'<link rel="canonical" href="racing.html"><title>{label} | {esc(cfg["name"])}</title></head>'
            f'<body><p><a href="racing.html#{anchor}">{label}</a></p></body></html>')

    # ---------- about ----------
    about_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">The trainer</div><h1>Meet <span class="grad">Scott</span></h1></div></div>
<section><div class="wrap about">
{photo_html(cfg)}
<div class="story">{story_html(cfg) or '<p class="note">Scott\'s story is coming soon.</p>'}</div>
</div></section>{contact}"""
    (out_p / "about.html").write_text(page(cfg, "Meet Scott | " + cfg["name"], about_body, "about"))

    # ---------- become an owner ----------
    rate = own_cfg.get("dailyRate", 75)
    min_share = own_cfg.get("minShare", 1)
    try:
        rate_f = float(rate)
    except (TypeError, ValueError):
        rate_f = None
    def money(v):
        return f"${v:,.2f}".replace(".00", "")
    examples = ""
    if rate_f:
        ex_rows = "".join(
            f'<tr><td><b>{s}%</b></td><td>{money(rate_f * s / 100)}</td><td>{money(rate_f * s / 100 * 30)}</td></tr>'
            for s in (1, 5, 10, 25, 50)
            if s >= float(min_share)
        )
        examples = (
            '<div class="scroll" style="margin-top:18px"><table style="min-width:0"><thead><tr><th>Your share</th><th>Training per day</th>'
            f'<th>Training per 30 days</th></tr></thead><tbody>{ex_rows}</tbody></table></div>'
            f'<p class="note">Based on the {money(rate_f)}/day training rate. The horse\'s other expenses are split the same way.</p>'
        )
    by_name = {h["name"].upper(): h for h in horses}
    avail_cards = []
    for n, v in sorted(listed.items(), key=lambda kv: -kv[1]):
        if v <= 0:
            continue
        h = by_name.get(n.upper())
        rec = ""
        if h:
            st = horse_stats(h)
            rec = f'<div class="note">{st["starts"]} start{"" if st["starts"] == 1 else "s"} &middot; {st["w"]} win{"" if st["w"] == 1 else "s"} &middot; best {esc(st["best"] or "-")}</div>'
        avail_cards.append(
            f'<div class="card horse">{media_html(cfg, n)}<h3>{esc(n.title())}</h3>{rec}'
            f'<a class="play" href="owners.html?horse={quote(n.title())}#inquire">Ask about {esc(pct_txt(v))}</a></div>'
        )
    avail_html = (
        f'<div class="grid">{"".join(avail_cards)}</div>' if avail_cards else
        '<div class="card"><p class="note" style="margin:0">Shares open up as new horses join the barn. '
        'Send us a note below and we will tell you what is available right now.</p></div>'
    )
    opts = "".join(f'<option>{esc(n.title())}</option>' for n, v in sorted(listed.items()) if v > 0)
    email = (cfg.get("contact", {}).get("email") or "").strip()
    phone = (cfg.get("contact", {}).get("phone") or "").strip()
    reach = []
    if phone:
        reach.append(f'Call or text <a href="tel:{esc(phone)}">{esc(phone)}</a>')
    if email:
        reach.append(f'email <a href="mailto:{esc(email)}">{esc(email)}</a>')
    steps = [
        ("Pick a horse", "Browse the barn and pick the horse you want in on, or tell us your budget and we will suggest one."),
        ("Choose your share", f"Own as little as {esc(min_share)}% or as much as is available. Your share sets your part of the costs and the purse money."),
        ("Get licensed", "Owners need to be licensed to race. We walk you through the paperwork so it is quick and painless."),
        ("Enjoy race day", "Follow every start, get updates from the barn, and join us in the winner's circle when your horse wins."),
    ]
    steps_html = "".join(
        f'<div class="card own-step"><span>{i}</span><h3>{esc(t)}</h3><p>{d}</p></div>' for i, (t, d) in enumerate(steps, 1)
    )
    owners_css = (
        '<style>.own-steps{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}'
        '.own-step span{display:inline-grid;place-items:center;width:38px;height:38px;border-radius:50%;background:var(--flame);'
        'font:400 1.4rem/1 "Bebas Neue",Impact,sans-serif;margin-bottom:12px}.own-step h3{font-size:1.6rem;margin:0 0 6px}'
        '.own-step p{margin:0;color:var(--mute);font-size:.94rem}.own-form{display:grid;gap:14px;grid-template-columns:1fr 1fr;max-width:760px}'
        '.own-form label{display:grid;gap:6px;font:700 .68rem/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}'
        '.own-form .full{grid-column:1/-1}.own-form input,.own-form select,.own-form textarea{font:16px Inter,sans-serif;color:var(--text);'
        'background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:12px}.own-form textarea{min-height:110px;resize:vertical}'
        '.own-form input:focus,.own-form select:focus,.own-form textarea:focus{outline:none;border-color:var(--flame2)}'
        '@media(max-width:620px){.own-form{grid-template-columns:1fr}}section[id]{scroll-margin-top:90px}</style>'
    )
    owners_js = (
        "<script>(function(){var f=document.getElementById('own-form');if(!f)return;"
        "var q=new URLSearchParams(location.search).get('horse');if(q){var s=f.horse;"
        "for(var i=0;i<s.options.length;i++){if(s.options[i].text.toLowerCase()===q.toLowerCase()){s.selectedIndex=i;}}}"
        "f.addEventListener('submit',function(e){e.preventDefault();var d=new FormData(f);"
        "var body='Name: '+d.get('name')+'\\nEmail: '+d.get('email')+'\\nPhone: '+(d.get('phone')||'')+"
        "'\\nHorse: '+d.get('horse')+'\\nShare size: '+(d.get('share')||'')+'\\n\\n'+(d.get('msg')||'');"
        f"location.href='mailto:{email}?subject='+encodeURIComponent('Ownership inquiry: '+d.get('horse'))+'&body='+encodeURIComponent(body);"
        "});})();</script>"
    )
    form_html = (
        f'<form id="own-form" class="own-form card">'
        '<label>Name<input name="name" required autocomplete="name"></label>'
        '<label>Email<input name="email" type="email" required autocomplete="email"></label>'
        '<label>Phone<input name="phone" type="tel" autocomplete="tel"></label>'
        f'<label>Horse<select name="horse"><option>Any horse / not sure yet</option>{opts}</select></label>'
        f'<label class="full">Share size you have in mind<input name="share" placeholder="e.g. {esc(min_share)}%, 10%, or a monthly budget"></label>'
        '<label class="full">Questions<textarea name="msg" placeholder="Anything you want to know"></textarea></label>'
        '<div class="full"><button class="btn" type="submit" style="border:0;cursor:pointer">Send inquiry</button>'
        '<span class="note">Opens your email app with your details filled in.</span></div></form>'
    ) if email else ""
    owners_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">Fractional racehorse ownership</div><h1>Become an <span class="grad">Owner</span></h1>
<p class="tag" style="color:#d6d4cd;max-width:640px;margin:16px 0 24px">Own a piece of a Standardbred racing at The Meadows and Northfield Park, with shares starting at just {esc(min_share)}%. You get the race-day thrill without carrying a whole horse yourself.</p>
<a class="btn" href="#available">See available shares</a><a class="btn alt" href="#inquire">Ask a question</a></div></div>
<section><div class="wrap"><div class="eyebrow">How it works</div><h2>Four Steps to the Winner's Circle</h2>
<p class="sub">Scott trains every horse himself, and the family runs the barn. Owners get straight answers and real updates.</p>
<div class="own-steps">{steps_html}</div></div></section>
<section class="alt"><div class="wrap cols"><div><div class="eyebrow">The numbers</div><h2>What It Costs</h2>
<p class="sub" style="margin-bottom:0">Training is {money(rate_f) if rate_f else esc(rate)} a day per horse. Owners split the horse's costs and its purse earnings in proportion to their share, so a 10% owner pays 10% of the bills and collects 10% of what the horse earns.</p>
{examples}</div>
<div><div class="eyebrow">Good to know</div><h2>Why Own a Share</h2><div class="card"><p style="margin-top:0">&#10003; Shares as small as {esc(min_share)}%</p><p>&#10003; One trainer, hands-on with every horse</p><p>&#10003; Results and entries posted here automatically</p><p style="margin-bottom:0">&#10003; Racing at The Meadows and Northfield Park</p></div>
<p class="note">Racing carries real risk. Purses are never guaranteed, and a horse can earn less than it costs to keep.</p></div></div></section>
<section id="available"><div class="wrap"><div class="eyebrow">Open now</div><h2>Available Shares</h2>
<p class="sub">Horses with shares open for purchase. The red ring shows how much of each horse is available.</p>{avail_html}</div></section>
<section id="inquire" class="alt"><div class="wrap"><div class="eyebrow">Let's talk</div><h2>Get in Touch</h2>
<p class="sub">Tell us what you are interested in and we will follow up with the details on that horse.{(" " + " or ".join(reach) + ".") if reach else ""}</p>
{form_html}</div></section>{owners_js}"""
    (out_p / "owners.html").write_text(page(cfg, "Become an Owner | " + cfg["name"], owners_body, "owners",
        f"Own a share of a Scott Betts-trained Standardbred racehorse. Fractional shares from {min_share}%, training at ${rate}/day.", owners_css))

    mem = cfg.get("memoriam", {})
    ph = "".join(f"<p>{esc(p)}</p>" for p in cfg.get("phoenix", []))
    gal = "".join(
        f'<figure{" class=\'wide\'" if g.get("wide") else ""}><img src="{esc(g["src"])}" alt="{esc(g["alt"])}" loading="lazy">'
        + (f'<div class="mem-cap">{esc(g["caption"])}</div>' if g.get("caption") else "")
        + "</figure>"
        for g in mem.get("gallery", [])
    )
    hon = mem.get("honor", {})
    hon_paras = "".join(f"<p>{esc(p)}</p>" for p in hon.get("paragraphs", []))
    hon_facts = "".join(f"<li><b>{esc(k)}</b>{esc(v)}</li>" for k, v in hon.get("facts", []))
    hon_html = (
        f'<div class="mem-div"></div><div class="story" style="max-width:720px;margin:0 auto;text-align:center">'
        f'<h2>{esc(hon.get("name",""))}</h2><p class="note">{esc(hon.get("sub",""))}</p>{hon_paras}'
        + (f'<ul class="mem-facts">{hon_facts}</ul>' if hon_facts else "")
        + (f'<p class="note" style="margin-top:18px">{esc(hon.get("source",""))}</p>' if hon.get("source") else "")
        + "</div>"
    ) if hon else ""
    mem_css = '<style>.mem-gal{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin:34px 0 8px}.mem-gal figure{margin:0}.mem-gal img{width:100%;height:auto;display:block;border-radius:10px}.mem-gal .wide{grid-column:1/-1}.mem-cap{font-size:.8rem;opacity:.65;margin-top:6px;text-align:center}.mem-div{max-width:120px;height:1px;background:currentColor;opacity:.25;margin:56px auto}.mem-facts{list-style:none;padding:0;margin:22px auto 0;max-width:560px;text-align:left}.mem-facts li{padding:9px 0;border-bottom:1px solid rgba(255,255,255,.12)}.mem-facts b{display:inline-block;min-width:110px}</style>'
    memoriam_body = f"""
<div class="page-head memorial"><div class="wrap"><div class="eyebrow">In loving memory</div><h1>In <span class="grad">Memoriam</span></h1><p class="note" style="margin-top:14px">Phoenix Warrior N &middot; Our Honor Defend</p></div></div>
<section><div class="wrap"><div class="story" style="max-width:720px;margin:0 auto;text-align:center">
<h2>Phoenix Warrior N</h2><p class="note">2018 Meadows Horse of the Year</p>{ph}</div>
<div class="mem-gal">{gal}</div>
{hon_html}</div></section>{contact}"""
    (out_p / "memoriam.html").write_text(page(cfg, "In Memoriam | " + cfg["name"], memoriam_body, "memoriam", "Remembering Phoenix Warrior N, 2018 Meadows Horse of the Year, and Our Honor Defend.", mem_css))
    (out_p / "phoenix.html").write_text("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=memoriam.html\"><link rel=\"canonical\" href=\"memoriam.html\"><title>In Memoriam | " + esc(cfg["name"]) + "</title></head><body><p><a href=\"memoriam.html\">In Memoriam</a></p></body></html>")

    print(f"built {len(horses)} horses (+{len(pending)} pending), {len(all_rows)} starts -> {out_p}")

if __name__ == "__main__":
    main()
