#!/usr/bin/env python3
"""Scott Betts Racing static site generator.

Usage: python3 build.py <data.json> <config.json> <output_dir>
Pages: index, horses, results, replays, about, memoriam, phoenix (redirect)
"""
import html
import json
import re
import sys
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
    ("results.html", "Results", "results"),
    ("replays.html", "Replays", "replays"),
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

def media_html(cfg, name):
    m = {k.upper(): v for k, v in cfg.get("horseMedia", {}).items()}.get(name.upper())
    if not m:
        return ""
    st = "width:100%;height:auto;max-height:420px;object-fit:cover;display:block;border-radius:8px;margin-bottom:14px;background:#000"
    if m.get("video"):
        poster = f' poster="{esc(m["photo"])}"' if m.get("photo") else ""
        return f'<video controls playsinline preload="metadata"{poster} src="{esc(m["video"])}" style="{st}"></video>'
    return f'<img src="{esc(m["photo"])}" alt="{esc(name.title())}" loading="lazy" style="{st}">'

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
            f'<div class="card">{"<br>".join(lines)}</div></div></section>'
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
<a class="btn" href="horses.html">Meet the Horses</a><a class="btn alt" href="replays.html">Watch Replays</a>
</div></div>
{stats_html}
</div></div>
<section><div class="wrap cols">
<div><div class="eyebrow">Live from the track</div><h2>Recent Results</h2><p class="sub">Updated automatically every morning from TrackMaster race charts.</p>
{results_table(all_rows, 8)}
<p><a href="results.html">See all results &rarr;</a></p></div>
<div><div class="eyebrow">Coming up</div><h2>Up Next</h2><p class="sub">Entries for the coming days.</p>{upcoming_block(upcoming)}</div>
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
    horses_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">The barn</div><h1>The <span class="grad">Horses</span></h1></div></div>
<section><div class="wrap"><p class="sub">Current members of the stable. Records reflect starts this season.</p>
<div class="grid">{"".join(cards) or '<p class="note">Roster coming soon.</p>'}</div></div></section>{contact}"""
    (out_p / "horses.html").write_text(page(cfg, "The Horses | " + cfg["name"], horses_body, "horses"))

    # ---------- results ----------
    res_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">Every start, every week</div><h1>Race <span class="grad">Results</span></h1></div></div>
<section><div class="wrap"><p class="sub">{len(raced)} starts, {len(wins)} wins this season. Winners are highlighted. Click Chart for the full TrackMaster race chart.</p>
{results_table(all_rows)}</div></section>
<section class="alt"><div class="wrap"><div class="eyebrow">Coming up</div><h2>Upcoming</h2>{upcoming_block(upcoming)}</div></section>"""
    (out_p / "results.html").write_text(page(cfg, "Results | " + cfg["name"], res_body, "results"))

    # ---------- replays ----------
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
        vid_html = f'<section class="alt"><div class="wrap"><div class="eyebrow">Featured</div><h2>Race Videos</h2><div class="vids">{items}</div></div></section>'
    rep_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">Relive it</div><h1>Race <span class="grad">Replays</span></h1></div></div>
<section><div class="wrap"><h2>Win Circle</h2>
<p class="sub">Every winner this season. Each button opens the TrackMaster chart, which has the video replay.</p>
<div class="wins">{"".join(win_cards) or '<p class="note">No wins yet this season.</p>'}</div></div></section>
{vid_html}
<section class="alt"><div class="wrap"><h2>Every Start</h2><p class="sub">Chart and replay links for the most recent races.</p>{results_table(all_rows, 24)}</div></section>"""
    (out_p / "replays.html").write_text(page(cfg, "Replays | " + cfg["name"], rep_body, "replays"))

    # ---------- about ----------
    about_body = f"""
<div class="page-head"><div class="wrap"><div class="eyebrow">The trainer</div><h1>Meet <span class="grad">Scott</span></h1></div></div>
<section><div class="wrap about">
{photo_html(cfg)}
<div class="story">{story_html(cfg) or '<p class="note">Scott\'s story is coming soon.</p>'}</div>
</div></section>{contact}"""
    (out_p / "about.html").write_text(page(cfg, "Meet Scott | " + cfg["name"], about_body, "about"))

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
