"""
CrisisIQ - Weather Tool (MCP-style)
Fetches real-time weather data from OpenWeatherMap API.
"""

import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_weather(city: str) -> dict:
    """
    MCP Tool: Fetch current weather data for a given city.

    Args:
        city: Name of the city to fetch weather for.

    Returns:
        Structured dict with weather information or error details.
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        logger.error("WEATHER_API_KEY not set in environment variables.")
        return {"error": "Weather API key not configured."}

    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",  # Use Celsius
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(OPENWEATHER_BASE_URL, params=params)
            response.raise_for_status()
            raw = response.json()

        # Parse and normalize the response
        weather_data = {
            "city": raw.get("name", city),
            "country": raw.get("sys", {}).get("country", "N/A"),
            "temperature_c": raw.get("main", {}).get("temp", None),
            "feels_like_c": raw.get("main", {}).get("feels_like", None),
            "humidity_percent": raw.get("main", {}).get("humidity", None),
            "condition": raw.get("weather", [{}])[0].get("description", "unknown"),
            "condition_main": raw.get("weather", [{}])[0].get("main", "unknown"),
            "wind_speed_ms": raw.get("wind", {}).get("speed", None),
            "wind_gust_ms": raw.get("wind", {}).get("gust", None),
            "visibility_m": raw.get("visibility", None),
            "pressure_hpa": raw.get("main", {}).get("pressure", None),
            "cloudiness_percent": raw.get("clouds", {}).get("all", None),
            "rain_1h": raw.get("rain", {}).get("1h", 0),
            "rain_3h": raw.get("rain", {}).get("3h", 0),
            "snow_1h": raw.get("snow", {}).get("1h", 0),
            "snow_3h": raw.get("snow", {}).get("3h", 0),
            "latitude": raw.get("coord", {}).get("lat"),
            "longitude": raw.get("coord", {}).get("lon"),
        }

        logger.info(f"Weather fetched successfully for city: {city}")
        return weather_data

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"City not found: {city}")
            return {"error": f"City '{city}' not found. Please check the city name."}
        logger.error(f"HTTP error fetching weather for {city}: {e}")
        return {"error": f"Weather API returned status {e.response.status_code}."}

    except httpx.RequestError as e:
        logger.error(f"Network error fetching weather for {city}: {e}")
        return {"error": "Network error while fetching weather data."}

    except Exception as e:
        logger.error(f"Unexpected error in weather tool: {e}")
        return {"error": "An unexpected error occurred in the weather tool."}


def classify_weather_risk(weather_data: dict) -> dict:
    """
    Analyze weather data and compute a weather-based risk score.

    Risk factors:
      - Wind speed >= 20 m/s → HIGH
      - Wind speed >= 10 m/s → MEDIUM
      - Condition keywords (storm, thunderstorm, tornado, hurricane) → HIGH
      - Condition keywords (rain, drizzle, snow) → MEDIUM

    Returns:
        dict with 'score' (0-100) and 'factors' list.
    """
    if "error" in weather_data:
        return {"score": 0, "level": "UNKNOWN", "factors": [weather_data["error"]]}

    score = 0
    factors = []

    wind_speed = weather_data.get("wind_speed_ms") or 0
    condition = (weather_data.get("condition") or "").lower()
    condition_main = (weather_data.get("condition_main") or "").lower()

    # Wind speed risk
    if wind_speed >= 28:
        score += 45
        factors.append(f"Extreme wind speed: {wind_speed} m/s")
    elif wind_speed >= 18:
        score += 30
        factors.append(f"High wind speed: {wind_speed} m/s")
    elif wind_speed >= 10:
        score += 16
        factors.append(f"Moderate wind speed: {wind_speed} m/s")

    gust_speed = weather_data.get("wind_gust_ms") or 0
    if gust_speed >= 30:
        score += 15
        factors.append(f"Strong wind gusts: {gust_speed} m/s")

    # Condition-based risk
    HIGH_RISK_CONDITIONS = ["thunderstorm", "tornado", "hurricane", "typhoon", "squall", "cyclone"]
    MEDIUM_RISK_CONDITIONS = ["rain", "drizzle", "snow", "sleet", "hail", "storm", "squall"]

    for kw in HIGH_RISK_CONDITIONS:
        if kw in condition or kw in condition_main:
            score += 40
            factors.append(f"Severe weather condition: {condition}")
            break

    if not any(kw in condition or kw in condition_main for kw in HIGH_RISK_CONDITIONS):
        for kw in MEDIUM_RISK_CONDITIONS:
            if kw in condition or kw in condition_main:
                score += 22
                factors.append(f"Adverse weather condition: {condition}")
                break

    rain_1h = weather_data.get("rain_1h") or 0
    rain_3h = weather_data.get("rain_3h") or 0
    snow_1h = weather_data.get("snow_1h") or 0
    snow_3h = weather_data.get("snow_3h") or 0
    precipitation = max(rain_1h, rain_3h, snow_1h, snow_3h)

    if precipitation >= 20:
        score += 30
        factors.append(f"Heavy precipitation: {precipitation} mm")
    elif precipitation >= 5:
        score += 14
        factors.append(f"Moderate precipitation: {precipitation} mm")

    # Humidity extreme
    humidity = weather_data.get("humidity_percent") or 0
    if humidity >= 90:
        score += 6
        factors.append(f"Very high humidity: {humidity}%")
    elif humidity >= 80:
        score += 3
        factors.append(f"High humidity: {humidity}%")

    # Visibility and pressure
    visibility = weather_data.get("visibility_m") or 10000
    if visibility <= 1000:
        score += 12
        factors.append(f"Low visibility: {visibility} m")
    elif visibility <= 4000:
        score += 6
        factors.append(f"Reduced visibility: {visibility} m")

    pressure = weather_data.get("pressure_hpa") or 1013
    if pressure <= 990:
        score += 8
        factors.append(f"Low pressure: {pressure} hPa")
    elif pressure >= 1030:
        score += 3
        factors.append(f"High pressure: {pressure} hPa")

    # Cap at 100
    score = min(score, 100)

    if score >= 60:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"score": score, "level": level, "factors": factors}
