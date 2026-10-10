"""The prompt sent to the local model."""

from __future__ import annotations

from .context import Context

SYSTEM = """You design short outdoor "field cards" that get people off their screens.
Reply with ONLY a JSON object, no prose and no code fences, with exactly these keys:
  "title": string, 2 to 6 words
  "intro": string, one or two sentences (max 35 words) about what this outing is
  "steps": array of 3 to 5 objects {"do": string, "minutes": integer}
  "notice": array of 3 short strings: things to look, listen or feel for
  "bring": array of 0 to 4 short strings (nothing electronic)
  "log_prompts": array of 2 short questions to answer on paper afterwards
Rules:
- Every step is done on foot, within about 1 km of the start, using eyes, ears and hands.
- Never tell the person to use a phone, an app, a camera or a search engine.
- The step minutes must add up to the minutes available.
- Do not write sunrise, sunset or clock times. The printed card adds them.
- Be concrete and sensory: count, compare, listen, touch, follow. Max 25 words per step.
- Match the mood, season, weather and time of day you are given. Keep it safe and ordinary."""


def build_prompt(ctx: Context) -> tuple[str, str]:
    lines = [
        f"Minutes available: {ctx.minutes}",
        f"Time of day: {ctx.phase}",
        f"Season: {ctx.season} ({ctx.season_note})",
        f"Mood: {ctx.mood}",
        f"Going with: {ctx.companions}",
        f"Where: {ctx.terrain}",
    ]
    if ctx.weather:
        lines.append(f"Weather: {ctx.weather}")
    if ctx.phase in ("night", "dusk"):
        lines.append("It is dark or nearly dark: stay close to home on a familiar lit route, mostly stationary.")
    return SYSTEM, "\n".join(lines)
