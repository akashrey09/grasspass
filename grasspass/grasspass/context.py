"""Everything the card needs to know that code can compute better than a model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .sun import sun_times

CALM_MOODS = {"calm", "tired", "stressed", "anxious", "low", "burnt out", "burnt-out", "slow"}

_SEASON_NOTES = {
    "summer-sa": ("summer", "Hot and dry. Go early or late, carry water, rest in shade."),
    "monsoon": ("monsoon", "Wet season. Expect puddles, fresh growth, frogs and insects; watch footing."),
    "post-monsoon": ("post-monsoon", "Greening after the rains, migrant birds arriving, still warm at midday."),
    "winter-sa": ("winter", "Cool and dry, the best walking season. Mornings can be misty."),
    "winter": ("winter", "Cold. Bare branches make birds and bark easy to see."),
    "spring": ("spring", "New leaves, early flowers, birdsong picking up."),
    "summer": ("summer", "Long days and heat. Shade and water matter."),
    "autumn": ("autumn", "Turning leaves, falling seeds, low golden light."),
}


def season_for(lat: float, lon: float, month: int) -> tuple[str, str]:
    """Return (season name, one-line note). Handles South Asia's monsoon calendar."""
    if 5 <= lat <= 35 and 60 <= lon <= 100:
        if month in (3, 4, 5):
            return _SEASON_NOTES["summer-sa"]
        if month in (6, 7, 8, 9):
            return _SEASON_NOTES["monsoon"]
        if month in (10, 11):
            return _SEASON_NOTES["post-monsoon"]
        return _SEASON_NOTES["winter-sa"]
    m = month if lat >= 0 else ((month + 5) % 12) + 1
    if m in (12, 1, 2):
        return _SEASON_NOTES["winter"]
    if m in (3, 4, 5):
        return _SEASON_NOTES["spring"]
    if m in (6, 7, 8):
        return _SEASON_NOTES["summer"]
    return _SEASON_NOTES["autumn"]


@dataclass
class Context:
    now: datetime
    lat: float
    lon: float
    tz_hours: float
    sunrise: datetime | None
    sunset: datetime | None
    phase: str
    season: str
    season_note: str
    minutes: int
    back_by: datetime
    weather: str
    terrain: str
    mood: str
    companions: str
    minutes_requested: int

    @property
    def capped(self) -> bool:
        return self.minutes < self.minutes_requested


def day_phase(now: datetime, sunrise: datetime | None, sunset: datetime | None) -> str:
    if sunrise is None or sunset is None:
        return "daytime"
    if now < sunrise - timedelta(minutes=30):
        return "night"
    if now < sunrise + timedelta(minutes=60):
        return "dawn"
    if now >= sunset + timedelta(minutes=60):
        return "night"
    if now >= sunset + timedelta(minutes=20):
        return "dusk"
    if now >= sunset - timedelta(minutes=60):
        return "golden hour"
    f = (now - sunrise) / (sunset - sunrise)
    if f < 0.4:
        return "morning"
    if f < 0.65:
        return "midday"
    return "afternoon"


def build_context(
    *,
    lat: float,
    lon: float,
    tz_hours: float,
    now: datetime,
    minutes: int,
    mood: str = "curious",
    weather: str = "",
    terrain: str = "neighbourhood streets and any green space nearby",
    companions: str = "solo",
) -> Context:
    sunrise, sunset, _ = sun_times(now.date(), lat, lon, tz_hours)
    phase = day_phase(now, sunrise, sunset)
    season, note = season_for(lat, lon, now.month)

    capped = minutes
    if phase == "night":
        capped = min(minutes, 30)
    elif phase == "dusk":
        capped = min(minutes, 20)
    elif sunset is not None and now < sunset:
        left = int((sunset - now).total_seconds() // 60)
        capped = min(minutes, max(left, 10))

    return Context(
        now=now,
        lat=lat,
        lon=lon,
        tz_hours=tz_hours,
        sunrise=sunrise,
        sunset=sunset,
        phase=phase,
        season=season,
        season_note=note,
        minutes=capped,
        back_by=now + timedelta(minutes=capped),
        weather=weather.strip(),
        terrain=terrain.strip(),
        mood=mood.strip().lower() or "curious",
        companions=companions.strip() or "solo",
        minutes_requested=minutes,
    )
