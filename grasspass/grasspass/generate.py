"""Model first, offline bank as the safety net."""

from __future__ import annotations

from .card import CardError, validate
from .context import Context
from .fallback import build_fallback
from .llm import LLMConfig, LLMError, chat_json
from .prompts import build_prompt


def generate(
    ctx: Context,
    llm_cfg: LLMConfig | None = None,
    offline: bool = False,
    seed: int = 0,
    retries: int = 1,
) -> tuple[dict, str, list[str]]:
    """Return (card, source, notes). Never raises: worst case is the offline bank."""
    notes: list[str] = []

    if not offline:
        cfg = llm_cfg or LLMConfig.from_env()
        system, user = build_prompt(ctx)
        for _ in range(retries + 1):
            try:
                raw = chat_json(cfg, system, user)
                return validate(raw, ctx.minutes), f"model:{cfg.model}", notes
            except LLMError as exc:
                notes.append(str(exc))
                if not exc.retryable:
                    break
            except CardError as exc:
                notes.append(f"model card rejected: {exc}")

    card = validate(build_fallback(ctx, seed), ctx.minutes)
    return card, "offline-bank", notes
