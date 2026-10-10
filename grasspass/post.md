---
title: "Grass Pass: a local-model field card that makes the screen the shortest part of your walk"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

## What I Built

Most "get outside" software has a design problem: it asks you to stare at a screen so it can tell you to look up.

Grass Pass does the opposite. It's a small command-line tool that writes you a one-page field card for a walk and then gets out of the way. You tell it where you are, how long you have and how you feel. It hands back a card with three to five steps (each with minutes), things to notice, what to bring, a couple of questions to answer on paper afterwards, and a large **Back by 17:34** box.

The card is a single HTML page with no network requests. Print it, or keep it open on your phone, then lock the screen and go. The tool's whole footprint on your day is the few seconds before you leave.

It's for people who sit at a laptop most of the day (me included) and whose plan to "go for a walk" dies at the question: to where, and to do what?

## Demo

A real run: 4:49 pm in Vadodara, 45 minutes, feeling curious.

```
GRASS PASS #001  GOLDEN HOUR CHASE
Afternoon · post-monsoon · 45 min
Back by 17:34   (sunrise 06:31, sunset 18:17)

Low sun makes everything look different. Spend the best light of the day on purpose.

  [ ] 1. (13 min) Walk with the sun at your side, never looking straight at it, and find three things lit gold.
  [ ] 2. (9 min) Find the longest shadow you can and pace out its length.
  [ ] 3. (9 min) Turn around and notice the colours on everything lit from behind.
  [ ] 4. (14 min) Sit somewhere with a wide view and watch the light change until time is up.

Notice:
  - Shadows stretching across the ground
  - Colours you only see in low light
  - Which way birds and insects are moving
  - Greening after the rains, migrant birds arriving, still warm at midday.

Bring: Water

Afterwards, on paper:
  ? What was the best-lit thing you saw?
  ? How long was your longest shadow in paces?

Lock the screen. Put the phone away. The card is all you need.
```

That particular card came from the built-in offline quest bank, which takes over when no model is running. With a model running, the same computed facts go into the prompt and the model writes the card. The sample page and a screenshot are in the repo's `examples/` folder.

### Taking it outside

**TODO: fill this in after you actually go.** Where you went, what time you left, which model wrote the card, which step surprised you, what the card got wrong. Two or three honest sentences beat a polished paragraph.

## Code

{% embed https://github.com/akashrey09/grasspass %}

Python standard library only, so there's nothing to install: clone it and run `python -m grasspass quest`. Fifty tests.

```
grasspass/
  sun.py        sunrise/sunset from the NOAA equations
  context.py    season, time of day, daylight-capped minutes
  prompts.py    what the model is asked
  llm.py        OpenAI-compatible client (Ollama, llama.cpp, LM Studio, vLLM)
  card.py       validation of anything that claims to be a card
  fallback.py   offline quest bank
  generate.py   model first, bank as the safety net
  render.py     HTML / Markdown / terminal
  journal.py    plain-file log
```

## How I Built It

**The open pieces.** The default model is Gemma 3 (4B) running locally in Ollama. The client talks to `/v1/chat/completions`, the protocol that Ollama, llama.cpp's server, LM Studio and vLLM all expose, so changing the model or the whole runtime is two environment variables:

```bash
export GRASSPASS_MODEL=qwen3:8b
export GRASSPASS_BASE_URL=http://localhost:8080/v1
```

**Model for ideas, code for facts.** The first design decision was deciding what the model is *not* allowed to do. Small models are good company and bad arithmetic, and "when does the sun set?" is exactly the sentence where being confidently wrong means walking home in the dark. So sunrise and sunset come from the NOAA solar equations, about forty lines of stdlib maths. The season and time of day derive from those, and the **Back by** time is computed, never generated. Ask for two hours at 5:40 pm and the code shortens it before the model sees the request. The prompt then forbids the model from writing clock times at all. I checked the sun code against London's midsummer sunrise and sunset, the equator at the equinox, and Tromsø's polar day and night.

**The model's reply is untrusted input.** Small open models rarely follow a schema perfectly. Every reply goes through a validator that parses it, clamps lengths, rescales the step minutes to add up to the time available, and rejects any card whose steps tell you to use a phone, app, camera or search engine, which would defeat the whole point. The core loop:

```python
for _ in range(retries + 1):
    try:
        raw = chat_json(cfg, system, user)
        return validate(raw, ctx.minutes), f"model:{cfg.model}", notes
    except LLMError as exc:
        notes.append(str(exc))
        if not exc.retryable:      # server isn't running: don't wait around
            break
    except CardError as exc:
        notes.append(f"model card rejected: {exc}")
card = validate(build_fallback(ctx, seed), ctx.minutes)   # never raises
```

**No model? Still a walk.** Nine hand-written quests (a sound map, three trees, a golden-hour chase, a dawn chorus and so on) are the safety net. They're chosen by time of day and mood, and they pass the same validator. A stressed mood only gets the calm ones; after dark you only get the quiet, close-to-home ones. The tool therefore works on a machine that has never heard of Ollama, which is the case I'd bet on most strongly out on a trail.

**Testing without a model.** I tested the client against a small fake server that speaks the same `/v1/chat/completions` contract, and drove it through good replies, chatty replies, malformed JSON, HTTP 500 and 404, a sneaky "open an app" step, and a refused connection. To check the tests had teeth, I deliberately broke the device-word filter and the night-time cap; each break made tests fail.

Running the real CLI also caught a mistake in my own design. The first version of `stats` printed "80,000 seconds outside for every second on the screen." That's technically true and completely misleading, because it only counted generation time and ignored the time spent reading and logging. I replaced it with plain numbers.

**TODO: one honest line on your first run against a real model:** which model, which laptop, how many seconds a card took, and how many replies the validator rejected. The fake server isn't a model, and the post is stronger with a real measurement in it.

## Why Does Open Innovation Matter?

Four reasons, each tied to something in the build.

**A trail has no signal.** The design only works if making a card needs nothing but your own laptop. A hosted API ties the walk to a connection at exactly the moment you're about to leave one. With a local model, and an offline bank for when there's no model, the whole pipeline runs on a plane.

**The inputs are personal.** The prompt holds where you are, when you're leaving and how you feel, and the journal records when you went out and for how long. That's a diary of your movements and mood. Keeping it on your own machine isn't a feature I added; it's what falls out of there being no server.

**You control the engine.** The validator exists *because* models are swappable: a 4B model and an 8B model fail differently. With open weights and a standard protocol I can change the model, temperature, prompt and retry policy, and see exactly what each change does.

**Retries are free.** Rejecting a bad card and asking again costs a few seconds and nothing else. Against a metered API, a loop that treats the model as untrusted input is a budget decision. Locally it's a `for` loop.

**Where closed would have been better.** A frontier hosted model would write richer cards, in more varied voices, and would probably be rejected less often. A 4B model is a modest author. I accepted that trade on purpose: a plainer card that works offline and keeps your location private is a better walking companion than a more elegant one that needs a signal. The validator and the offline bank are what make the plain-but-reliable choice viable.

**Limits.** Weather is whatever you pass in `--weather`; there's no live feed. Sun times ignore terrain and elevation, so the back-by time is a guide, not a guarantee. It writes ideas for walks; it doesn't identify species or judge whether a place is safe.

## My Agent Session

I built Grass Pass in a working session with an AI coding agent (Claude). I supplied the theme; the agent proposed the architecture, wrote the code and tests, and ran them.

**TODO: say what you decided or changed yourself, and embed or link the session (for example with DevRelay). Delete this section if you'd rather not include one.**

## Prize Categories

- **Best Use of Gemma**: the default model is Gemma 3, running locally.

**TODO: keep this only if you actually ran it on Gemma. Otherwise delete this section.**
