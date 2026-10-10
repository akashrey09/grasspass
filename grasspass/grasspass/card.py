"""Validation of a field card, whether it came from a model or the offline bank.

Small open-weight models are good at ideas and bad at following a schema, so the
model's output is treated as untrusted input: it is parsed, bounded, rescaled to
the time available, and rejected if it tells the person to pick up a device.
"""

from __future__ import annotations

import re
import textwrap

# The whole point is the screen being the shortest part of the experience.
FORBIDDEN = re.compile(
    r"\b(phone|smartphone|apps?|scroll\w*|google\w*|search online|instagram|tiktok|"
    r"social media|screens?|qr code|download\w*|website|camera|photo\w*|selfie\w*)\b",
    re.IGNORECASE,
)


class CardError(ValueError):
    """The card is unusable and should be regenerated or replaced."""


def fit_minutes(weights: list[float], total: int) -> list[int]:
    """Scale positive weights to whole minutes, each at least 1, summing to total."""
    if total < len(weights):
        raise CardError(f"{total} minutes is too little for {len(weights)} steps")
    s = sum(weights) or 1.0
    scaled = [max(1, round(w * total / s)) for w in weights]
    # Nudge the largest steps until the sum is exact.
    while sum(scaled) != total:
        diff = total - sum(scaled)
        i = scaled.index(max(scaled)) if diff < 0 else scaled.index(min(scaled))
        scaled[i] = max(1, scaled[i] + (1 if diff > 0 else -1))
        if diff < 0 and all(v == 1 for v in scaled):
            break
    return scaled


def _text(value, limit: int, field: str) -> str:
    if not isinstance(value, str):
        raise CardError(f"{field} must be text")
    s = " ".join(value.split())
    if not s:
        raise CardError(f"{field} is empty")
    return textwrap.shorten(s, width=limit, placeholder="…")


def _text_list(value, lo: int, hi: int, limit: int, field: str) -> list[str]:
    if not isinstance(value, list):
        raise CardError(f"{field} must be a list")
    items = [_text(v, limit, field) for v in value if isinstance(v, str) and v.strip()]
    if len(items) < lo:
        raise CardError(f"{field} needs at least {lo} items")
    return items[:hi]


def validate(raw, minutes: int) -> dict:
    """Return a clean card dict or raise CardError."""
    if not isinstance(raw, dict):
        raise CardError("card is not an object")

    title = _text(raw.get("title"), 48, "title")
    intro = _text(raw.get("intro"), 240, "intro")

    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not 3 <= len(steps_raw) <= 6:
        raise CardError("steps must be a list of 3 to 6 items")
    texts: list[str] = []
    weights: list[float] = []
    for item in steps_raw:
        if isinstance(item, str):
            texts.append(_text(item, 200, "step"))
            weights.append(1.0)
        elif isinstance(item, dict):
            texts.append(_text(item.get("do"), 200, "step"))
            try:
                w = float(item.get("minutes", 1))
            except (TypeError, ValueError):
                w = 1.0
            weights.append(w if w > 0 else 1.0)
        else:
            raise CardError("step must be text or an object")
    mins = fit_minutes(weights, minutes)
    steps = [{"do": t, "minutes": m} for t, m in zip(texts, mins)]

    notice = _text_list(raw.get("notice"), 2, 5, 120, "notice")
    bring = _text_list(raw.get("bring", []), 0, 5, 60, "bring")
    log_prompts = _text_list(raw.get("log_prompts"), 1, 3, 120, "log_prompts")

    for field_name, chunks in (
        ("title", [title]),
        ("steps", texts),
        ("notice", notice),
        ("bring", bring),
    ):
        for chunk in chunks:
            hit = FORBIDDEN.search(chunk)
            if hit:
                raise CardError(f"{field_name} mentions a device ({hit.group(0)!r})")

    return {
        "title": title,
        "intro": intro,
        "steps": steps,
        "notice": notice,
        "bring": bring,
        "log_prompts": log_prompts,
    }
