"""Tests for the weather integration module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from kruppai.core.weather import (
    WeatherData,
    _manual_fallback,
    _weather_code_to_text,
    fetch_weather_sync,
)


class TestFetchWeatherSuccess:
    """Test successful weather API calls."""

    def test_fetch_weather_success(self) -> None:
        """Mock httpx to return a valid Open-Meteo response."""
        mock_response_data = {
            "daily": {
                "temperature_2m_max": [72.5],
                "temperature_2m_min": [45.2],
                "precipitation_sum": [0.0],
                "wind_speed_10m_max": [12.3],
                "weather_code": [2],
            }
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("kruppai.core.weather.httpx.Client", return_value=mock_client):
            result = fetch_weather_sync(39.7392, -104.9903, "2026-02-13")

        assert isinstance(result, WeatherData)
        assert result.high_f == 72.5
        assert result.low_f == 45.2
        assert result.precipitation_in == 0.0
        assert result.wind_mph == 12.3
        assert result.conditions == "Partly Cloudy"
        assert result.source == "open_meteo"


class TestFetchWeatherFailure:
    """Test weather API failure and fallback behavior."""

    def test_fetch_weather_api_failure(self) -> None:
        """On timeout or network error, should fall back to manual entry."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("kruppai.core.weather.httpx.Client", return_value=mock_client):
            result = fetch_weather_sync(39.7392, -104.9903, "2026-02-13")

        assert isinstance(result, WeatherData)
        assert result.source == "manual"
        assert result.conditions == "Manual entry required"
        assert result.high_f is None
        assert result.low_f is None

    def test_manual_fallback_returns_placeholder(self) -> None:
        """The manual fallback should return a placeholder with source='manual'."""
        result = _manual_fallback()
        assert result.source == "manual"
        assert result.conditions == "Manual entry required"
        assert result.high_f is None


class TestWeatherCodeMapping:
    """Test WMO weather code to text mapping."""

    def test_weather_code_mapping(self) -> None:
        """Verify known WMO codes map to expected text."""
        assert _weather_code_to_text(0) == "Clear Sky"
        assert _weather_code_to_text(1) == "Mainly Clear"
        assert _weather_code_to_text(2) == "Partly Cloudy"
        assert _weather_code_to_text(3) == "Overcast"
        assert _weather_code_to_text(45) == "Fog"
        assert _weather_code_to_text(61) == "Slight Rain"
        assert _weather_code_to_text(65) == "Heavy Rain"
        assert _weather_code_to_text(71) == "Slight Snowfall"
        assert _weather_code_to_text(75) == "Heavy Snowfall"
        assert _weather_code_to_text(95) == "Thunderstorm"

    def test_weather_code_unknown(self) -> None:
        """Unknown codes should return a descriptive string."""
        result = _weather_code_to_text(999)
        assert "Unknown" in result
        assert "999" in result
