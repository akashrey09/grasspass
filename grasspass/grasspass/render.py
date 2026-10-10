"""Turn a card into something you can carry outside: paper, a saved page, or terminal text."""

from __future__ import annotations

from html import escape

from .context import Context

PLEDGE = "Lock the screen. Put the phone away. The card is all you need."


def _hm(dt) -> str:
    return dt.strftime("%H:%M") if dt else "--:--"


def _meta_line(ctx: Context) -> str:
    return f"{ctx.phase.capitalize()} · {ctx.season} · {ctx.minutes} min"


def to_text(card: dict, ctx: Context, entry_id: int, source: str) -> str:
    out = [
        f"GRASS PASS #{entry_id:03d}  {card['title'].upper()}",
        _meta_line(ctx),
        f"Back by {_hm(ctx.back_by)}   (sunrise {_hm(ctx.sunrise)}, sunset {_hm(ctx.sunset)})",
        "",
        card["intro"],
        "",
    ]
    for i, s in enumerate(card["steps"], 1):
        out.append(f"  [ ] {i}. ({s['minutes']} min) {s['do']}")
    out += ["", "Notice:"] + [f"  - {n}" for n in card["notice"]]
    if card["bring"]:
        out += ["", "Bring: " + ", ".join(card["bring"])]
    out += ["", "Afterwards, on paper:"] + [f"  ? {p}" for p in card["log_prompts"]]
    out += ["", PLEDGE, f"(made by {source})"]
    return "\n".join(out)


def to_markdown(card: dict, ctx: Context, entry_id: int, source: str) -> str:
    out = [
        f"# {card['title']}",
        f"*Grass Pass #{entry_id:03d} · {_meta_line(ctx)}*",
        "",
        f"**Back by {_hm(ctx.back_by)}** (sunrise {_hm(ctx.sunrise)}, sunset {_hm(ctx.sunset)})",
        "",
        card["intro"],
        "",
        "## Steps",
    ]
    out += [f"- [ ] **{s['minutes']} min.** {s['do']}" for s in card["steps"]]
    out += ["", "## Notice"] + [f"- {n}" for n in card["notice"]]
    if card["bring"]:
        out += ["", "## Bring"] + [f"- {b}" for b in card["bring"]]
    out += ["", "## Afterwards, on paper"] + [f"- {p}" for p in card["log_prompts"]]
    out += ["", f"> {PLEDGE}", "", f"*Made by {source}.*", ""]
    return "\n".join(out)


_CSS = """
:root{--paper:#f6f1e4;--ink:#1f3a2b;--moss:#4f7a4b;--rule:#c9c0a6;--warm:#b4562b}
*{box-sizing:border-box}
body{margin:0;background:#e8e2d0;color:var(--ink);font:18px/1.45 Georgia,'Times New Roman',serif}
main{max-width:560px;margin:0 auto;padding:22px 18px 28px;background:var(--paper)}
header{border-bottom:3px double var(--ink);padding-bottom:10px;margin-bottom:14px}
.kicker{font:600 12px/1 system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--moss)}
h1{margin:6px 0 2px;font-size:32px;line-height:1.1}
.meta{font:14px system-ui,sans-serif;color:#3b5546}
.back{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:14px 0;
 padding:10px 14px;border:2px solid var(--warm);border-radius:10px;background:#fbe9dc}
.back b{font:700 28px system-ui,sans-serif;color:var(--warm)}
.back span{font:13px/1.3 system-ui,sans-serif;text-align:right}
h2{font:700 13px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--moss);margin:20px 0 6px}
ol{list-style:none;padding:0;margin:0}
li.step{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--rule)}
.box{flex:none;width:26px;height:26px;border:2.5px solid var(--ink);border-radius:5px;margin:3px 12px 0 0}
.mins{font:700 13px system-ui,sans-serif;color:var(--moss);display:block}
ul{margin:0;padding-left:20px}
.lines div{border-bottom:1px solid var(--ink);height:34px}
.pledge{margin-top:22px;padding:10px 14px;background:var(--ink);color:var(--paper);border-radius:10px;
 font:600 15px system-ui,sans-serif;text-align:center}
footer{margin-top:10px;font:12px system-ui,sans-serif;color:#5f7568;text-align:center}
@media print{body{background:#fff}main{max-width:none;padding:0}@page{size:A5;margin:12mm}}
"""


def to_html(card: dict, ctx: Context, entry_id: int, source: str) -> str:
    e = escape
    steps = "".join(
        f'<li class="step"><span class="box"></span><div><span class="mins">{s["minutes"]} MIN</span>{e(s["do"])}</div></li>'
        for s in card["steps"]
    )
    notice = "".join(f"<li>{e(n)}</li>" for n in card["notice"])
    bring = (
        f"<h2>Bring</h2><ul>{''.join(f'<li>{e(b)}</li>' for b in card['bring'])}</ul>" if card["bring"] else ""
    )
    prompts = "".join(f"<p>{e(p)}</p><div class='lines'><div></div><div></div></div>" for p in card["log_prompts"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(card['title'])} · Grass Pass #{entry_id:03d}</title>
<style>{_CSS}</style></head>
<body><main>
<header><div class="kicker">Grass Pass #{entry_id:03d}</div><h1>{e(card['title'])}</h1>
<div class="meta">{e(_meta_line(ctx))}</div></header>
<p>{e(card['intro'])}</p>
<div class="back"><div><div class="kicker">Back by</div><b>{_hm(ctx.back_by)}</b></div>
<span>sunrise {_hm(ctx.sunrise)}<br>sunset {_hm(ctx.sunset)}</span></div>
<h2>Do</h2><ol>{steps}</ol>
<h2>Notice</h2><ul>{notice}</ul>
{bring}
<h2>Afterwards, on paper</h2>{prompts}
<div class="pledge">{e(PLEDGE)}</div>
<footer>Made by {e(source)} · no network needed to read this page</footer>
</main></body></html>
"""
