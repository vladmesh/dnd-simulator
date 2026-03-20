"""Pure functions for geography calculations.

Stateless formulas for temperature, daylight, and season determination.
No side effects, no dependencies on layer state.
"""

from __future__ import annotations

import math

from dnd_simulator.core.models import Season, TerrainType, WeatherCondition


def get_season(month: int, latitude: float) -> Season:
    """Determine season from month and hemisphere."""
    if latitude < 0:
        # Southern hemisphere: shift by 6 months
        month = (month + 5) % 12 + 1

    if month in (3, 4, 5):
        return Season.SPRING
    if month in (6, 7, 8):
        return Season.SUMMER
    if month in (9, 10, 11):
        return Season.AUTUMN
    return Season.WINTER


def calculate_base_temperature(
    latitude: float,
    month: int,
    hour: int,
    elevation: float,
) -> float:
    """Calculate temperature without weather effects.

    Based on:
    - Latitude: equator ~28C base, poles ~-5C
    - Season: up to +/-12C variation at high latitudes
    - Time of day: +/-5C (min at 05:00, max at 15:00)
    - Elevation: -6.5C per 1000m (standard lapse rate)
    """
    # Base from latitude (cosine curve)
    lat_rad = math.radians(latitude)
    base = 28.0 * math.cos(lat_rad) - 5.0

    # Seasonal variation (stronger at higher latitudes)
    season_amplitude = 12.0 * (abs(latitude) / 90.0)
    day_of_year = (month - 1) * 30 + 15
    # Peak warmth ~day 200 (mid-July) for northern hemisphere
    if latitude >= 0:
        season_offset = math.cos(2 * math.pi * (day_of_year - 200) / 360)
    else:
        season_offset = math.cos(2 * math.pi * (day_of_year - 15) / 360)
    base += season_amplitude * season_offset

    # Diurnal variation (peak at 15:00, trough at 05:00)
    base += 5.0 * math.cos(2 * math.pi * (hour - 15) / 24)

    # Elevation lapse rate
    base -= 6.5 * (elevation / 1000.0)

    return round(base, 1)


_WEATHER_TEMP_MODIFIERS: dict[WeatherCondition, float] = {
    WeatherCondition.CLEAR: 0.0,
    WeatherCondition.CLOUDY: -1.0,
    WeatherCondition.LIGHT_RAIN: -2.0,
    WeatherCondition.HEAVY_RAIN: -4.0,
    WeatherCondition.STORM: -5.0,
    WeatherCondition.SNOW: -2.0,
    WeatherCondition.BLIZZARD: -6.0,
    WeatherCondition.FOG: -1.0,
}


def apply_weather_temperature_modifier(base_temp: float, weather: WeatherCondition) -> float:
    """Adjust temperature based on current weather."""
    return round(base_temp + _WEATHER_TEMP_MODIFIERS.get(weather, 0.0), 1)


def calculate_daylight_hours(latitude: float, month: int) -> float:
    """Calculate hours of daylight from latitude and time of year.

    Uses simplified solar declination formula.
    """
    day_of_year = (month - 1) * 30 + 15
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))

    lat_rad = math.radians(latitude)
    dec_rad = math.radians(declination)

    cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)

    # Clamp for polar regions
    if cos_hour_angle < -1.0:
        return 24.0  # midnight sun
    if cos_hour_angle > 1.0:
        return 0.0  # polar night

    hour_angle = math.degrees(math.acos(cos_hour_angle))
    return round(2.0 * hour_angle / 15.0, 1)


_EARTH_RADIUS_KM = 6371.0


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using the Haversine formula."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(_EARTH_RADIUS_KM * c, 1)


_BASE_WALKING_SPEED_KMH = 5.0

_TERRAIN_SPEED_MODIFIERS: dict[TerrainType, float] = {
    TerrainType.PLAINS: 1.0,
    TerrainType.COAST: 0.9,
    TerrainType.FOREST: 0.7,
    TerrainType.HILLS: 0.6,
    TerrainType.DESERT: 0.6,
    TerrainType.SWAMP: 0.5,
    TerrainType.MOUNTAINS: 0.4,
    TerrainType.TUNDRA: 0.7,
}

_WEATHER_SPEED_MODIFIERS: dict[WeatherCondition, float] = {
    WeatherCondition.CLEAR: 1.0,
    WeatherCondition.CLOUDY: 1.0,
    WeatherCondition.FOG: 0.8,
    WeatherCondition.LIGHT_RAIN: 0.85,
    WeatherCondition.HEAVY_RAIN: 0.7,
    WeatherCondition.STORM: 0.5,
    WeatherCondition.SNOW: 0.6,
    WeatherCondition.BLIZZARD: 0.3,
}


def calculate_travel_hours(
    distance_km: float,
    terrain: TerrainType,
    weather: WeatherCondition,
    elevation_diff: float = 0.0,
) -> float:
    """Calculate travel time in hours.

    Accounts for terrain, weather, and elevation gain.
    Elevation gain adds 1 hour per 500m climbed (Naismith's rule).
    """
    terrain_mod = _TERRAIN_SPEED_MODIFIERS.get(terrain, 1.0)
    weather_mod = _WEATHER_SPEED_MODIFIERS.get(weather, 1.0)
    speed = _BASE_WALKING_SPEED_KMH * terrain_mod * weather_mod

    hours = distance_km / speed

    # Elevation gain penalty (only when climbing)
    if elevation_diff > 0:
        hours += elevation_diff / 500.0

    return round(hours, 1)


def is_daylight(latitude: float, month: int, hour: int) -> bool:
    """Check if it's currently daylight at the given location and time.

    Sunrise and sunset are symmetric around noon (12:00).
    """
    daylight = calculate_daylight_hours(latitude, month)
    if daylight >= 24.0:
        return True
    if daylight <= 0.0:
        return False
    sunrise = 12.0 - daylight / 2.0
    sunset = 12.0 + daylight / 2.0
    return sunrise <= hour < sunset
