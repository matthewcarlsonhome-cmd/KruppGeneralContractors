"""Weather data from Open-Meteo API. Free, no key required.

Provides current and historical weather data for daily field reports.
Uses the Open-Meteo API (https://open-meteo.com/) which requires no
API key and supports both forecast and historical queries.

WMO weather codes are mapped to human-readable condition strings
suitable for construction daily reports.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT_SECONDS = 10.0


@dataclass
class WeatherData:
    """Weather observation for a single day and location.

    Attributes:
        high_f: High temperature in Fahrenheit.
        low_f: Low temperature in Fahrenheit.
        conditions: Human-readable weather description (e.g., "Partly Cloudy").
        precipitation_in: Total precipitation in inches.
        wind_mph: Maximum wind speed in miles per hour.
        source: Data origin — 'open_meteo' or 'manual'.
    """

    high_f: float | None
    low_f: float | None
    conditions: str
    precipitation_in: float | None
    wind_mph: float | None
    source: str  # 'open_meteo' or 'manual'


def _build_params(lat: float, lng: float, date: str) -> dict[str, str]:
    """Build query parameters for the Open-Meteo API request.

    Args:
        lat: Latitude of the project site.
        lng: Longitude of the project site.
        date: ISO-8601 date string (YYYY-MM-DD).

    Returns:
        Dictionary of query parameters.
    """
    return {
        "latitude": str(lat),
        "longitude": str(lng),
        "start_date": date,
        "end_date": date,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }


def _parse_response(data: dict) -> WeatherData:
    """Parse an Open-Meteo JSON response into a WeatherData instance.

    Args:
        data: Parsed JSON response from the Open-Meteo API.

    Returns:
        Populated WeatherData with source='open_meteo'.

    Raises:
        KeyError: If expected fields are missing from the response.
    """
    daily = data["daily"]
    weather_code = daily["weather_code"][0] if daily.get("weather_code") else None
    conditions = _weather_code_to_text(weather_code) if weather_code is not None else "Unknown"

    return WeatherData(
        high_f=daily["temperature_2m_max"][0] if daily.get("temperature_2m_max") else None,
        low_f=daily["temperature_2m_min"][0] if daily.get("temperature_2m_min") else None,
        conditions=conditions,
        precipitation_in=daily["precipitation_sum"][0] if daily.get("precipitation_sum") else None,
        wind_mph=daily["wind_speed_10m_max"][0] if daily.get("wind_speed_10m_max") else None,
        source="open_meteo",
    )


def _manual_fallback() -> WeatherData:
    """Return a manual-entry placeholder when the API is unavailable.

    Returns:
        WeatherData with all values set to None and source='manual'.
    """
    return WeatherData(
        high_f=None,
        low_f=None,
        conditions="Manual entry required",
        precipitation_in=None,
        wind_mph=None,
        source="manual",
    )


async def fetch_weather(lat: float, lng: float, date: str) -> WeatherData:
    """Fetch weather for a specific date and location from Open-Meteo.

    Uses the async httpx client. Falls back to a manual-entry placeholder
    on any network or parsing error.

    Args:
        lat: Latitude of the project site.
        lng: Longitude of the project site.
        date: ISO-8601 date string (YYYY-MM-DD).

    Returns:
        WeatherData populated from the API or a manual fallback.
    """
    params = _build_params(lat, lng, date)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return _parse_response(data)
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Weather API request failed, falling back to manual: %s", exc)
        return _manual_fallback()


def fetch_weather_sync(lat: float, lng: float, date: str) -> WeatherData:
    """Fetch weather for a specific date and location from Open-Meteo.

    Synchronous version using httpx. Falls back to a manual-entry
    placeholder on any network or parsing error.

    Args:
        lat: Latitude of the project site.
        lng: Longitude of the project site.
        date: ISO-8601 date string (YYYY-MM-DD).

    Returns:
        WeatherData populated from the API or a manual fallback.
    """
    params = _build_params(lat, lng, date)
    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return _parse_response(data)
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Weather API request failed, falling back to manual: %s", exc)
        return _manual_fallback()


def _weather_code_to_text(code: int) -> str:
    """Convert a WMO weather interpretation code to human-readable text.

    WMO code table 4677 is used by Open-Meteo. Codes are grouped by
    severity and type of precipitation.

    Args:
        code: WMO weather code (0-99).

    Returns:
        Human-readable condition string suitable for daily reports.
    """
    wmo_codes: dict[int, str] = {
        0: "Clear Sky",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing Rime Fog",
        51: "Light Drizzle",
        53: "Moderate Drizzle",
        55: "Dense Drizzle",
        56: "Light Freezing Drizzle",
        57: "Dense Freezing Drizzle",
        61: "Slight Rain",
        63: "Moderate Rain",
        65: "Heavy Rain",
        66: "Light Freezing Rain",
        67: "Heavy Freezing Rain",
        71: "Slight Snowfall",
        73: "Moderate Snowfall",
        75: "Heavy Snowfall",
        77: "Snow Grains",
        80: "Slight Rain Showers",
        81: "Moderate Rain Showers",
        82: "Violent Rain Showers",
        85: "Slight Snow Showers",
        86: "Heavy Snow Showers",
        95: "Thunderstorm",
        96: "Thunderstorm with Slight Hail",
        99: "Thunderstorm with Heavy Hail",
    }
    return wmo_codes.get(code, f"Unknown (code {code})")
