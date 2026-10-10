import unittest
from datetime import date, datetime

from grasspass.card import CardError, FORBIDDEN, fit_minutes, validate
from grasspass.context import build_context, day_phase, season_for
from grasspass.fallback import BANK, build_fallback
from grasspass.render import to_html, to_markdown, to_text
from grasspass.sun import sun_times

VADODARA = dict(lat=22.3072, lon=73.1812, tz_hours=5.5)


def ctx_at(when: str, minutes=40, mood="curious", **kw):
    return build_context(now=datetime.strptime(when, "%Y-%m-%d %H:%M"), minutes=minutes, mood=mood, **VADODARA, **kw)


class SunTests(unittest.TestCase):
    def test_equator_equinox_is_about_twelve_hours(self):
        rise, sset, noon = sun_times(date(2026, 3, 20), 0.0, 0.0, 0.0)
        hours = (sset - rise).total_seconds() / 3600
        self.assertTrue(12.0 < hours < 12.25, hours)
        self.assertTrue(12 <= noon.hour <= 12 and noon.minute < 15)

    def test_london_midsummer_matches_published_times(self):
        rise, sset, _ = sun_times(date(2026, 6, 21), 51.5074, -0.1278, 1.0)
        self.assertLess(abs((rise.hour * 60 + rise.minute) - (4 * 60 + 43)), 4)
        self.assertLess(abs((sset.hour * 60 + sset.minute) - (21 * 60 + 21)), 4)

    def test_polar_day_and_night_return_none(self):
        self.assertEqual(sun_times(date(2026, 6, 21), 69.65, 18.96, 2.0)[:2], (None, None))
        self.assertEqual(sun_times(date(2026, 12, 21), 69.65, 18.96, 1.0)[:2], (None, None))

    def test_vadodara_october_is_sane(self):
        rise, sset, _ = sun_times(date(2026, 10, 9), **{"lat": 22.3072, "lon": 73.1812, "tz_hours": 5.5})
        self.assertTrue(6 <= rise.hour <= 7)
        self.assertTrue(18 <= sset.hour <= 18)


class ContextTests(unittest.TestCase):
    def test_south_asia_monsoon_calendar(self):
        self.assertEqual(season_for(22.3, 73.2, 10)[0], "post-monsoon")
        self.assertEqual(season_for(22.3, 73.2, 7)[0], "monsoon")
        self.assertEqual(season_for(22.3, 73.2, 1)[0], "winter")

    def test_southern_hemisphere_is_flipped(self):
        self.assertEqual(season_for(-33.9, 151.2, 1)[0], "summer")
        self.assertEqual(season_for(51.5, -0.1, 1)[0], "winter")

    def test_phases_follow_the_sun(self):
        self.assertEqual(ctx_at("2026-10-09 05:00").phase, "night")
        self.assertEqual(ctx_at("2026-10-09 06:45").phase, "dawn")
        self.assertEqual(ctx_at("2026-10-09 09:00").phase, "morning")
        self.assertEqual(ctx_at("2026-10-09 16:49").phase, "afternoon")
        self.assertEqual(ctx_at("2026-10-09 17:40").phase, "golden hour")
        self.assertEqual(ctx_at("2026-10-09 18:45").phase, "dusk")
        self.assertEqual(ctx_at("2026-10-09 21:00").phase, "night")

    def test_polar_phase_does_not_crash(self):
        self.assertEqual(day_phase(datetime(2026, 6, 21, 12, 0), None, None), "daytime")

    def test_minutes_are_capped_by_daylight(self):
        c = ctx_at("2026-10-09 17:40", minutes=120)
        self.assertLess(c.minutes, 120)
        self.assertTrue(c.capped)
        self.assertLessEqual(c.back_by, c.sunset)

    def test_night_and_dusk_caps(self):
        self.assertEqual(ctx_at("2026-10-09 21:00", minutes=120).minutes, 30)
        self.assertEqual(ctx_at("2026-10-09 18:45", minutes=120).minutes, 20)

    def test_no_cap_when_there_is_plenty_of_light(self):
        c = ctx_at("2026-10-09 08:00", minutes=40)
        self.assertEqual(c.minutes, 40)
        self.assertFalse(c.capped)


class FitMinutesTests(unittest.TestCase):
    def test_sums_exactly_and_never_below_one(self):
        for total in (10, 17, 40, 90):
            for weights in ([2, 3, 2, 2], [1, 1, 1], [5, 1, 2, 2, 7]):
                got = fit_minutes(weights, total)
                self.assertEqual(sum(got), total, (weights, total, got))
                self.assertTrue(all(g >= 1 for g in got))

    def test_too_little_time_is_an_error(self):
        with self.assertRaises(CardError):
            fit_minutes([1, 1, 1, 1], 3)


GOOD = {
    "title": "Hedge Detective",
    "intro": "Follow a hedge for ten minutes and see who lives in it.",
    "steps": [
        {"do": "Walk along a hedge slowly.", "minutes": 5},
        {"do": "Count the kinds of leaf you can see.", "minutes": 5},
        {"do": "Stop and listen for movement inside.", "minutes": 5},
    ],
    "notice": ["Spider webs", "Fruit or seeds", "Any small birds"],
    "bring": ["Water"],
    "log_prompts": ["What lived in the hedge?"],
}


class ValidateTests(unittest.TestCase):
    def test_good_card_is_rescaled_to_available_minutes(self):
        card = validate(GOOD, 30)
        self.assertEqual(sum(s["minutes"] for s in card["steps"]), 30)

    def test_accepts_plain_string_steps(self):
        raw = dict(GOOD, steps=["Walk.", "Look up.", "Sit down."])
        self.assertEqual(sum(s["minutes"] for s in validate(raw, 15)["steps"]), 15)

    def test_bad_minutes_value_does_not_crash(self):
        raw = dict(GOOD, steps=[{"do": "Walk.", "minutes": "soon"}, {"do": "Look.", "minutes": -4}, {"do": "Sit.", "minutes": 2}])
        self.assertEqual(sum(s["minutes"] for s in validate(raw, 12)["steps"]), 12)

    def test_rejects_device_instructions(self):
        for bad in ("Take a photo of the tree.", "Open an app to identify the bird.", "Check your phone for the time."):
            raw = dict(GOOD, steps=[{"do": bad, "minutes": 5}] + GOOD["steps"][1:])
            with self.assertRaises(CardError, msg=bad):
                validate(raw, 30)

    def test_rejects_structural_problems(self):
        for raw in ("nope", {}, dict(GOOD, steps=[]), dict(GOOD, title=""), dict(GOOD, notice=["one"]), dict(GOOD, log_prompts=[])):
            with self.assertRaises(CardError):
                validate(raw, 30)

    def test_long_text_is_shortened_not_rejected(self):
        raw = dict(GOOD, intro="word " * 200)
        self.assertLessEqual(len(validate(raw, 30)["intro"]), 240)


class FallbackTests(unittest.TestCase):
    def test_every_bank_quest_passes_validation_at_every_length(self):
        for q in BANK:
            for minutes in (10, 20, 40, 120):
                raw = {
                    "title": q["title"],
                    "intro": q["intro"],
                    "steps": [{"do": t, "minutes": w} for t, w in q["steps"]],
                    "notice": q["notice"],
                    "bring": q["bring"],
                    "log_prompts": q["log"],
                }
                card = validate(raw, minutes)
                self.assertEqual(sum(s["minutes"] for s in card["steps"]), minutes)

    def test_bank_never_mentions_devices(self):
        for q in BANK:
            text = " ".join([q["title"], q["intro"]] + [t for t, _ in q["steps"]] + q["notice"] + q["bring"] + q["log"])
            self.assertIsNone(FORBIDDEN.search(text), q["key"])

    def test_every_phase_has_a_quest(self):
        for when in ("05:00", "06:45", "09:00", "12:30", "16:49", "17:40", "18:45", "21:00"):
            card = build_fallback(ctx_at(f"2026-10-09 {when}"))
            self.assertTrue(card["steps"], when)

    def test_dark_hours_never_get_a_daytime_quest(self):
        for seed in range(30):
            self.assertEqual(build_fallback(ctx_at("2026-10-09 21:00"), seed)["title"] in {"The Sound Map", "Sit Spot", "Evening Eyes and Ears"}, True)

    def test_calm_mood_gets_a_calm_quest(self):
        calm_titles = {q["title"] for q in BANK if q["calm"]}
        for seed in range(30):
            self.assertIn(build_fallback(ctx_at("2026-10-09 16:49", mood="stressed"), seed)["title"], calm_titles)

    def test_same_day_same_place_is_deterministic(self):
        c = ctx_at("2026-10-09 16:49")
        self.assertEqual(build_fallback(c, 3), build_fallback(c, 3))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.ctx = ctx_at("2026-10-09 16:49")
        self.card = validate(build_fallback(self.ctx), self.ctx.minutes)

    def test_back_by_time_is_printed_on_every_format(self):
        hm = self.ctx.back_by.strftime("%H:%M")
        for out in (
            to_html(self.card, self.ctx, 1, "offline-bank"),
            to_markdown(self.card, self.ctx, 1, "offline-bank"),
            to_text(self.card, self.ctx, 1, "offline-bank"),
        ):
            self.assertIn(hm, out)

    def test_html_is_self_contained_and_offline(self):
        html = to_html(self.card, self.ctx, 1, "offline-bank")
        for needle in ("http://", "https://", "src=", "<script", "@import", "url("):
            self.assertNotIn(needle, html)

    def test_html_escapes_model_text(self):
        card = dict(self.card, title="<script>alert(1)</script>")
        html = to_html(card, self.ctx, 1, "model:x")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_polar_card_renders_without_sun_times(self):
        ctx = build_context(lat=69.65, lon=18.96, tz_hours=2.0, now=datetime(2026, 6, 21, 12, 0), minutes=30)
        card = validate(build_fallback(ctx), ctx.minutes)
        self.assertIn("--:--", to_html(card, ctx, 1, "offline-bank"))


if __name__ == "__main__":
    unittest.main()
