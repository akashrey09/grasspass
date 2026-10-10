"""Sunrise and sunset from the NOAA solar equations.

Pure standard library, so it works with no network. The language model is never
asked for these numbers: arithmetic about daylight is exactly the kind of thing
a small model gets confidently wrong, and being wrong here means walking home
in the dark.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta


def _rad(d: float) -> float:
    return math.radians(d)


def _deg(r: float) -> float:
    return math.degrees(r)


def sun_times(day: date, lat: float, lon: float, tz_hours: float):
    """Return (sunrise, sunset, solar_noon) as naive local datetimes.

    sunrise and sunset are None during polar day or polar night.
    lon is degrees east, tz_hours is the UTC offset of the local clock.
    """
    lat = max(-89.9, min(89.9, lat))

    # Julian day at local solar noon (approximate is fine for this).
    jd = day.toordinal() + 1721424.5 + (12.0 - tz_hours) / 24.0
    t = (jd - 2451545.0) / 36525.0

    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    c = (
        math.sin(_rad(m)) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(_rad(2 * m)) * (0.019993 - 0.000101 * t)
        + math.sin(_rad(3 * m)) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(_rad(omega))

    mean_obliq = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    obliq = mean_obliq + 0.00256 * math.cos(_rad(omega))
    decl = _deg(math.asin(math.sin(_rad(obliq)) * math.sin(_rad(app_long))))

    y = math.tan(_rad(obliq / 2.0)) ** 2
    eq_time = 4.0 * _deg(
        y * math.sin(2 * _rad(l0))
        - 2.0 * e * math.sin(_rad(m))
        + 4.0 * e * y * math.sin(_rad(m)) * math.cos(2 * _rad(l0))
        - 0.5 * y * y * math.sin(4 * _rad(l0))
        - 1.25 * e * e * math.sin(2 * _rad(m))
    )

    cos_ha = math.cos(_rad(90.833)) / (math.cos(_rad(lat)) * math.cos(_rad(decl))) - math.tan(
        _rad(lat)
    ) * math.tan(_rad(decl))

    noon_utc_min = 720.0 - 4.0 * lon - eq_time
    base = datetime(day.year, day.month, day.day)

    def at(minutes_utc: float) -> datetime:
        return base + timedelta(minutes=minutes_utc + tz_hours * 60.0)

    noon = at(noon_utc_min)
    if cos_ha > 1.0 or cos_ha < -1.0:
        return None, None, noon

    ha = _deg(math.acos(cos_ha))
    return at(noon_utc_min - 4.0 * ha), at(noon_utc_min + 4.0 * ha), noon
