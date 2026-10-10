"""Offline quest bank, used when no local model is running.

Hand-written so the tool still hands you something good on a laptop with no
model installed at all. Every quest is validated by the same rules as model
output (see card.py), and the tests enforce that.
"""

from __future__ import annotations

import random

from .card import fit_minutes
from .context import CALM_MOODS, Context

_DAY = {"dawn", "morning", "midday", "afternoon", "golden hour", "daytime"}

BANK = [
    {
        "key": "sound-map",
        "title": "The Sound Map",
        "intro": "Listening turns an ordinary street into a place with layers. You are collecting sounds, not distance.",
        "phases": None,
        "calm": True,
        "steps": [
            ("Walk away from the loudest thing you can hear until it fades a little.", 2),
            ("Stand still, eyes closed, and count every separate sound: near, far, living, machine.", 3),
            ("Open your eyes and find the source of the farthest sound you can.", 2),
            ("Walk back slowly, trying to catch one new sound before you reach the start.", 2),
        ],
        "notice": [
            "The quietest sound hiding under all the others",
            "Which direction the birds are calling from",
            "How far away the farthest sound seems",
        ],
        "bring": ["Something to sit on"],
        "log": ["How many sounds did you count?", "Which one surprised you?"],
    },
    {
        "key": "three-trees",
        "title": "Three Trees",
        "intro": "Learn three neighbours you probably walk past every day, by touch and by sight.",
        "phases": _DAY,
        "calm": False,
        "steps": [
            ("Find three different kinds of tree within sight of each other.", 2),
            ("Touch the bark of each and describe it in one word.", 2),
            ("Compare their leaves: edge, shape, size, how they hang.", 3),
            ("Choose the one you would sit under and sit there without talking.", 3),
        ],
        "notice": [
            "Bark: smooth, ridged, flaking or sticky",
            "Where the leaf meets the branch",
            "Which tree has the most life on it",
        ],
        "bring": ["Pencil and paper for a quick sketch"],
        "log": ["Which tree did you choose, and why?", "What did the bark feel like?"],
    },
    {
        "key": "golden-chase",
        "title": "Golden Hour Chase",
        "intro": "Low sun makes everything look different. Spend the best light of the day on purpose.",
        "phases": {"golden hour", "afternoon"},
        "calm": False,
        "steps": [
            ("Walk with the sun at your side, never looking straight at it, and find three things lit gold.", 3),
            ("Find the longest shadow you can and pace out its length.", 2),
            ("Turn around and notice the colours on everything lit from behind.", 2),
            ("Sit somewhere with a wide view and watch the light change until time is up.", 3),
        ],
        "notice": [
            "Shadows stretching across the ground",
            "Colours you only see in low light",
            "Which way birds and insects are moving",
        ],
        "bring": ["Water"],
        "log": ["What was the best-lit thing you saw?", "How long was your longest shadow in paces?"],
    },
    {
        "key": "dawn-chorus",
        "title": "Dawn Chorus",
        "intro": "Early birds sing in layers. Sit still and pull the voices apart one at a time.",
        "phases": {"dawn", "morning"},
        "calm": True,
        "steps": [
            ("Find a spot with open sky around you and sit down.", 2),
            ("Wait for the first bird call and note which direction it comes from.", 2),
            ("Make a tally on paper for each different voice you can separate.", 4),
            ("Pick one voice and describe it: rising, falling, buzzing, whistling.", 2),
        ],
        "notice": [
            "Which voice starts first",
            "Whether calls overlap or take turns",
            "A call you cannot place",
        ],
        "bring": ["Pencil and paper", "Something to sit on"],
        "log": ["How many different voices did you count?", "Which call would you know again?"],
    },
    {
        "key": "cloud-ledger",
        "title": "The Cloud Ledger",
        "intro": "Read the sky like a ledger: sort it, make a prediction, then check yourself.",
        "phases": {"morning", "midday", "afternoon", "daytime"},
        "calm": True,
        "steps": [
            ("Find somewhere you can sit or lie back and see a lot of sky.", 2),
            ("Sort the clouds into layers and give each shape a name of your own.", 3),
            ("Write down a prediction for the next half hour: which way, how fast, will it change?", 2),
            ("Wait, watch, and check your prediction before you leave.", 3),
        ],
        "notice": [
            "Whether high and low clouds move differently",
            "The edge where blue meets white",
            "Wind on your skin compared with cloud speed",
        ],
        "bring": ["Pencil and paper"],
        "log": ["Was your prediction right?", "What shape did you name that you will remember?"],
    },
    {
        "key": "texture-hunt",
        "title": "Texture Hunt",
        "intro": "Five textures, one short walk. Hands first, eyes second.",
        "phases": _DAY,
        "calm": False,
        "steps": [
            ("Find something rough, smooth, soft, cool and warm. Touch only things that are clearly clean and safe.", 5),
            ("Rank your five from favourite to least favourite.", 2),
            ("Rub a leaf you recognise between your fingers and smell it.", 2),
        ],
        "notice": [
            "How the same material feels in sun and in shade",
            "A surface that looks smooth but is not",
            "Something that is warm for no obvious reason",
        ],
        "bring": [],
        "log": ["What was your favourite texture?", "What felt different from how it looked?"],
    },
    {
        "key": "sit-spot",
        "title": "Sit Spot",
        "intro": "Find one place and let it show you what it has been doing without you.",
        "phases": None,
        "calm": True,
        "steps": [
            ("Walk a few minutes and stop at the first place that feels pleasant to sit.", 2),
            ("Sit and do nothing but notice, for most of your time.", 6),
            ("Sketch a small map of everything within arm's reach.", 2),
        ],
        "notice": [
            "The smallest living thing you can see",
            "Something that moved when you were not looking",
            "What you stopped hearing after a few minutes",
        ],
        "bring": ["Something to sit on", "Pencil and paper"],
        "log": ["What did the spot do while you sat?", "Would you come back here?"],
    },
    {
        "key": "night-sky",
        "title": "Evening Eyes and Ears",
        "intro": "Stay close to home and let your senses adjust to the dark.",
        "phases": {"dusk", "night"},
        "calm": True,
        "steps": [
            ("Walk a lit route you know well and stop where the sky opens up.", 3),
            ("Let your eyes adjust for three minutes without looking down.", 3),
            ("Find the brightest point of light overhead and see whether it twinkles.", 2),
            ("Listen for the evening sounds. What has changed since daytime?", 2),
        ],
        "notice": [
            "Whether the brightest light twinkles or stays steady",
            "Night sounds that daylight hides",
            "How much dimmer the sky is than the streetlights",
        ],
        "bring": ["A small torch for the way back"],
        "log": ["What did you see overhead?", "What sound belongs to the evening?"],
    },
    {
        "key": "litter-loop",
        "title": "The Tidy Loop",
        "intro": "A short loop that leaves the place a little better than you found it.",
        "phases": _DAY,
        "calm": False,
        "steps": [
            ("Walk a loop near home carrying a bag.", 3),
            ("Pick up litter that is safe to touch, aiming for ten pieces. Skip glass and anything sharp.", 4),
            ("Sort what you found: what is it, and where does it collect?", 2),
            ("Dispose of it properly and wash your hands.", 1),
        ],
        "notice": [
            "Where litter gathers: corners, drains, fence lines",
            "The most common kind of rubbish",
            "Wildlife using the places people neglect",
        ],
        "bring": ["A bag", "Gloves if you have them"],
        "log": ["How many pieces did you collect?", "What was the most common item?"],
    },
]


def build_fallback(ctx: Context, seed: int = 0) -> dict:
    candidates = [q for q in BANK if q["phases"] is None or ctx.phase in q["phases"]]
    if ctx.mood in CALM_MOODS:
        calm = [q for q in candidates if q["calm"]]
        candidates = calm or candidates

    rng = random.Random(ctx.now.toordinal() * 100003 + int(abs(ctx.lat) * 10) * 131 + int(abs(ctx.lon) * 10) + seed)
    q = rng.choice(candidates)

    texts = [t for t, _ in q["steps"]]
    mins = fit_minutes([w for _, w in q["steps"]], ctx.minutes)
    notice = list(q["notice"])
    notice.append(ctx.season_note)

    return {
        "title": q["title"],
        "intro": q["intro"],
        "steps": [{"do": t, "minutes": m} for t, m in zip(texts, mins)],
        "notice": notice,
        "bring": list(q["bring"]),
        "log_prompts": list(q["log"]),
    }
