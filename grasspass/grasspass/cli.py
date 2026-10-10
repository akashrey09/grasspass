"""Command line: quest, done, stats, list."""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime

from . import __version__, journal
from .context import build_context
from .generate import generate
from .llm import LLMConfig
from .render import to_html, to_markdown, to_text


def _local_tz_hours() -> float:
    off = datetime.now().astimezone().utcoffset()
    return off.total_seconds() / 3600.0 if off else 0.0


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "card"


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now().replace(second=0, microsecond=0)
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        raise SystemExit("--now must look like '2026-10-09 16:49'")


def cmd_quest(args: argparse.Namespace) -> int:
    cfg = journal.load_config()
    lat = args.lat if args.lat is not None else cfg.get("lat")
    lon = args.lon if args.lon is not None else cfg.get("lon")
    if lat is None or lon is None:
        print("Need a location: pass --lat and --lon (add --save-location to remember them).", file=sys.stderr)
        return 2
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        print("Latitude must be -90..90 and longitude -180..180.", file=sys.stderr)
        return 2
    if not 10 <= args.minutes <= 240:
        print("--minutes must be between 10 and 240.", file=sys.stderr)
        return 2
    tz = args.tz if args.tz is not None else cfg.get("tz", _local_tz_hours())
    if args.save_location:
        journal.save_config({"lat": lat, "lon": lon, "tz": tz})

    ctx = build_context(
        lat=lat,
        lon=lon,
        tz_hours=tz,
        now=_parse_now(args.now),
        minutes=args.minutes,
        mood=args.mood,
        weather=args.weather,
        terrain=args.terrain,
        companions=args.with_,
    )

    llm_cfg = LLMConfig.from_env()
    if args.model:
        llm_cfg.model = args.model
    if args.base_url:
        llm_cfg.base_url = args.base_url

    t0 = time.perf_counter()
    card, source, notes = generate(ctx, llm_cfg=llm_cfg, offline=args.offline, seed=args.seed)
    gen_seconds = time.perf_counter() - t0

    entry_id = journal.next_id()
    cards_dir = journal.home() / "cards"
    cards_dir.mkdir(exist_ok=True)
    stem = f"{entry_id:03d}-{_slug(card['title'])}"
    html_path = cards_dir / f"{stem}.html"
    md_path = cards_dir / f"{stem}.md"
    html_path.write_text(to_html(card, ctx, entry_id, source), encoding="utf-8")
    md_path.write_text(to_markdown(card, ctx, entry_id, source), encoding="utf-8")

    journal.add(
        {
            "id": entry_id,
            "issued_at": ctx.now.isoformat(timespec="minutes"),
            "title": card["title"],
            "source": source,
            "minutes_planned": ctx.minutes,
            "gen_seconds": round(gen_seconds, 2),
            "status": "issued",
            "minutes_outside": None,
            "note": None,
            "html": str(html_path),
        }
    )

    print(to_text(card, ctx, entry_id, source))
    print()
    if ctx.capped:
        print(f"Shortened from {ctx.minutes_requested} to {ctx.minutes} minutes to keep you out of the dark.")
    for n in notes:
        print(f"note: {n}")
    if source == "offline-bank" and not args.offline:
        print("note: used the offline quest bank instead of a model.")
    print(f"Saved: {html_path}")
    print(f"Generated in {gen_seconds:.1f}s. Now go.")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    try:
        e = journal.mark_done(args.id, args.minutes, args.note, datetime.now())
    except KeyError:
        print(f"No quest #{args.id}.", file=sys.stderr)
        return 1
    print(f"Logged #{e['id']} {e['title']}: {args.minutes} min outside.")
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    s = journal.stats()
    print(f"Quests issued:    {s['issued']}")
    print(f"Quests completed: {s['done']}")
    print(f"Time outside:     {s['minutes_outside']} min")
    print(f"Spent generating: {s['generating_seconds']} s of waiting on cards")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    for e in journal.load():
        mark = "x" if e["status"] == "done" else " "
        extra = f" ({e['minutes_outside']} min)" if e.get("minutes_outside") else ""
        print(f"[{mark}] #{e['id']:03d} {e['issued_at']}  {e['title']}{extra}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grasspass", description="Make a screen-free field card, then go outside.")
    p.add_argument("--version", action="version", version=f"grasspass {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quest", help="generate a field card")
    q.add_argument("--lat", type=float)
    q.add_argument("--lon", type=float)
    q.add_argument("--tz", type=float, help="UTC offset in hours (default: this computer's)")
    q.add_argument("--minutes", type=int, default=40)
    q.add_argument("--mood", default="curious")
    q.add_argument("--weather", default="", help='free text, e.g. "hot, humid, overcast"')
    q.add_argument("--terrain", default="neighbourhood streets and any green space nearby")
    q.add_argument("--with", dest="with_", default="solo", help="solo, friends, a child, a dog...")
    q.add_argument("--now", help="override the clock: '2026-10-09 16:49'")
    q.add_argument("--offline", action="store_true", help="skip the model, use the built-in quest bank")
    q.add_argument("--model", help="override GRASSPASS_MODEL")
    q.add_argument("--base-url", help="override GRASSPASS_BASE_URL")
    q.add_argument("--seed", type=int, default=0, help="change the offline bank's pick")
    q.add_argument("--save-location", action="store_true")
    q.set_defaults(func=cmd_quest)

    d = sub.add_parser("done", help="log a finished quest")
    d.add_argument("id", type=int)
    d.add_argument("--minutes", type=int, required=True, help="minutes you actually spent outside")
    d.add_argument("--note", default="")
    d.set_defaults(func=cmd_done)

    sub.add_parser("stats", help="outside time vs screen time").set_defaults(func=cmd_stats)
    sub.add_parser("list", help="list quests").set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
