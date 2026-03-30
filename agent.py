"""
CrisisIQ - Core AI Disaster Intelligence Agent

This agent follows the ADK (Agent Development Kit) design pattern:
  1. Receive user query
  2. Extract intent (city name)
  3. Invoke MCP tools (weather + news) in parallel
  4. Reason over combined results
  5. Generate a structured natural language response

MCP (Model Context Protocol) tools are implemented as async functions
in the tools/ package, each with a strict input/output contract.
"""

import re
import asyncio
import logging
from typing import Optional

from tools.weather_tool import fetch_weather, classify_weather_risk
from tools.news_tool import fetch_disaster_news, classify_news_risk

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Known city aliases / common name mappings
# -----------------------------------------------------------------------------
CITY_ALIASES = {
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "bangalore": "Bengaluru",
    "new delhi": "Delhi",
}

KNOWN_CITIES = [
    "Mumbai", "Chennai", "Kolkata", "Delhi", "Bengaluru", "Hyderabad",
    "Pune", "Ahmedabad", "Surat", "Jaipur", "Lucknow", "Kanpur",
    "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam", "Patna",
    "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad",
    "Meerut", "Rajkot", "New York", "London", "Paris", "Tokyo",
    "Los Angeles", "Sydney", "Singapore", "Toronto", "Dubai",
    "Hong Kong", "Shanghai", "Beijing", "Bangkok", "Seoul",
    "Mexico City", "Istanbul", "Moscow", "São Paulo", "Buenos Aires",
    "Cairo", "Lagos", "Johannesburg"
]

# Common disaster signal words used in user queries
DISASTER_SIGNAL_WORDS = [
    "cyclone", "flood", "earthquake", "storm", "tsunami",
    "hurricane", "tornado", "risk", "alert", "disaster",
    "danger", "safe", "warning"
]


# -----------------------------------------------------------------------------
# Step 1 – Intent Extraction
# -----------------------------------------------------------------------------

def extract_city_from_query(query: str) -> Optional[str]:
    """
    Extract a city name from a free-form user query.

    Strategy:
      - Match "in <City>", "near <City>", "for <City>", "at <City>"
      - Match "Is <City> at risk" / "Will <City> be"
      - Match common known city names anywhere in the query
      - Fallback: extract capitalized words that aren't common stop words
    """
    query_clean = query.strip()
    query_lower = query_clean.lower()

    # Pattern 1: explicit preposition before city
    pattern1 = re.search(
        r"\b(?:in|near|for|at|around|about)\s+([A-Za-z\s]{2,30}?)(?:\s+(?:at|is|safe|risk|today|now|area|region)|[?,!.]|$)",
        query_clean,
        re.IGNORECASE,
    )
    if pattern1:
        candidate = pattern1.group(1).strip()
        if candidate and candidate.lower() not in {
            "risk", "safe", "today", "now", "area", "region", "alert", "disaster"
        }:
            return _normalize_city(candidate)

    # Pattern 2: "Is <City> at risk" / "Will <City> be"
    pattern2 = re.search(
        r"\b(?:is|will|can)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:at|be|face|experience|get)",
        query_clean,
    )
    if pattern2:
        candidate = pattern2.group(1).strip()
        return _normalize_city(candidate)

    # Pattern 3: known city names anywhere in the query
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city.lower())}\b", query_lower):
            return _normalize_city(city)

    # Pattern 4: any capitalized word(s) not in exclusion list
    exclusions = {
        "Is", "Any", "Are", "Will", "What", "How", "When", "Where",
        "Should", "Can", "Do", "Does", "The", "A", "An", "Alert",
        "Disaster", "Risk", "Today", "Near", "Me", "I", "You",
    }
    tokens = query_clean.split()
    city_tokens = []
    for token in tokens:
        cleaned = re.sub(r"[^A-Za-z]", "", token)
        if cleaned and cleaned[0].isupper() and cleaned not in exclusions:
            city_tokens.append(cleaned)
        elif city_tokens:
            break  # stop collecting once sequence breaks

    if city_tokens:
        return _normalize_city(" ".join(city_tokens))

    return None


def _normalize_city(city: str) -> str:
    """Apply alias mapping and title-case normalization."""
    lower = city.lower()
    if lower in CITY_ALIASES:
        return CITY_ALIASES[lower]
    return city.title()


# -----------------------------------------------------------------------------
# Step 2 – MCP Tool Orchestration
# -----------------------------------------------------------------------------

async def run_mcp_tools(city: str) -> dict:
    """
    Invoke MCP tools concurrently using asyncio.gather.

    Returns raw tool outputs for downstream reasoning.
    """
    logger.info(f"[MCP] Invoking tools for city: {city}")

    # Run both tools in parallel (MCP parallel tool invocation pattern)
    weather_result, news_result = await asyncio.gather(
        fetch_weather(city),
        fetch_disaster_news(city),
        return_exceptions=False,
    )

    logger.info(f"[MCP] Tools completed. Weather: {'ok' if 'error' not in weather_result else 'error'}, "
                f"News: {'ok' if 'error' not in news_result else 'error'}")

    return {
        "weather": weather_result,
        "news": news_result,
    }


# -----------------------------------------------------------------------------
# Step 3 – Reasoning Engine
# -----------------------------------------------------------------------------

def reason_over_data(weather_data: dict, news_data: dict) -> dict:
    """
    Combined reasoning over weather + news data to produce:
      - Unified risk score (0–100)
      - Risk level: LOW / MEDIUM / HIGH
      - Contributing factors
      - Safety advice

    Scoring weights:
      - Weather risk: 50%
      - News risk:    50%
    """
    weather_risk = classify_weather_risk(weather_data)
    news_risk = classify_news_risk(news_data)

    # Weighted combined score
    weather_score = weather_risk.get("score", 0)
    news_score = news_risk.get("score", 0)
    combined_score = int(weather_score * 0.5 + news_score * 0.5)

    # Final risk level (take the maximum of both to be conservative)
    risk_levels = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "UNKNOWN": 0}
    w_level = weather_risk.get("level", "UNKNOWN")
    n_level = news_risk.get("level", "UNKNOWN")
    final_level = w_level if risk_levels.get(w_level, 0) >= risk_levels.get(n_level, 0) else n_level

    # Override: if either source is HIGH, final is HIGH
    if w_level == "HIGH" or n_level == "HIGH":
        final_level = "HIGH"

    all_factors = weather_risk.get("factors", []) + news_risk.get("factors", [])

    advice = _generate_advice(final_level, weather_data, news_data)
    categories = _infer_event_categories(weather_data, news_data)

    return {
        "risk_score": combined_score,
        "risk_level": final_level,
        "weather_risk": weather_risk,
        "news_risk": news_risk,
        "factors": all_factors,
        "event_categories": categories,
        "advice": advice,
    }


def _generate_advice(risk_level: str, weather_data: dict, news_data: dict) -> list[str]:
    """Generate contextual safety advice based on risk level and data."""
    advice = []

    if risk_level == "HIGH":
        advice = [
            "🚨 Avoid all non-essential travel immediately.",
            "🏠 Stay indoors and away from windows.",
            "📻 Monitor official government and meteorological alerts.",
            "🔦 Prepare an emergency kit (water, food, torch, medicines).",
            "📞 Keep emergency contacts (police: 100, ambulance: 108, NDRF: 1078) handy.",
            "🚫 Do not venture near rivers, coastlines, or low-lying areas.",
        ]
    elif risk_level == "MEDIUM":
        advice = [
            "⚠️ Exercise caution if travelling outdoors.",
            "☂️ Carry rain gear and be prepared for adverse weather.",
            "📡 Stay updated with local weather forecasts.",
            "🚗 Avoid waterlogged roads and underpasses.",
            "📋 Review your emergency preparedness plan.",
        ]
    else:  # LOW or UNKNOWN
        advice = [
            "✅ Conditions appear normal. Stay alert to changing weather.",
            "📱 Keep weather apps active for real-time updates.",
            "🌐 Periodically check local authority advisories.",
        ]

    # Additional context-specific advice
    wind_speed = weather_data.get("wind_speed_ms") or 0
    if wind_speed >= 15:
        advice.append(f"💨 High wind advisory: secure loose outdoor objects (wind: {wind_speed} m/s).")

    condition = (weather_data.get("condition") or "").lower()
    if "thunder" in condition or "storm" in condition:
        advice.append("⚡ Thunderstorm detected: avoid open areas and tall trees.")

    return advice


def _infer_event_categories(weather_data: dict, news_data: dict) -> list[str]:
    """Infer event categories based on weather conditions and news signals."""
    categories = set()
    weather_condition = (weather_data.get("condition") or "").lower()
    description_text = weather_condition

    if weather_data.get("rain_1h", 0) or weather_data.get("rain_3h", 0):
        categories.add("Flood / Heavy rain")
    if weather_data.get("snow_1h", 0) or weather_data.get("snow_3h", 0):
        categories.add("Snow / Winter risk")
    if any(keyword in weather_condition for keyword in ["thunderstorm", "storm", "squall", "hurricane", "cyclone", "tornado"]):
        categories.add("Severe storm")
    if any(keyword in weather_condition for keyword in ["heat", "heatwave"]):
        categories.add("Heat advisory")
    if any(keyword in weather_condition for keyword in ["drizzle", "rain", "shower"]):
        categories.add("Rain")
    if any(keyword in weather_condition for keyword in ["snow", "sleet", "hail"]):
        categories.add("Winter hazard")

    articles = news_data.get("articles", []) if isinstance(news_data, dict) else []
    news_text = " ".join([f"{article.get('title','')} {article.get('description','')}" for article in articles]).lower()
    description_text += " " + news_text

    if "flood" in news_text:
        categories.add("Flood")
    if "earthquake" in news_text or "tremor" in news_text:
        categories.add("Earthquake")
    if "wildfire" in news_text or "fire" in news_text:
        categories.add("Wildfire")
    if "tsunami" in news_text:
        categories.add("Tsunami")
    if "landslide" in news_text:
        categories.add("Landslide")
    if "drought" in news_text or "heatwave" in news_text:
        categories.add("Drought")
    if "evacuation" in news_text or "emergency" in news_text:
        categories.add("Emergency alert")

    if not categories:
        categories.add("General weather risk")

    return sorted(categories)


# -----------------------------------------------------------------------------
# Step 4 – Response Generation
# -----------------------------------------------------------------------------

def generate_report(city: str, weather_data: dict, news_data: dict, reasoning: dict) -> dict:
    """
    Build the final structured CrisisIQ report.

    Returns both a machine-readable dict and a human-readable text report.
    """
    risk_level = reasoning["risk_level"]
    risk_score = reasoning["risk_score"]

    # Build weather summary
    weather_summary = {}
    if "error" not in weather_data:
        weather_summary = {
            "temperature_c": weather_data.get("temperature_c"),
            "condition": weather_data.get("condition", "N/A").capitalize(),
            "wind_speed_ms": weather_data.get("wind_speed_ms"),
            "humidity_percent": weather_data.get("humidity_percent"),
            "feels_like_c": weather_data.get("feels_like_c"),
            "pressure_hpa": weather_data.get("pressure_hpa"),
            "latitude": weather_data.get("latitude"),
            "longitude": weather_data.get("longitude"),
            "condition_main": weather_data.get("condition_main"),
            "cloudiness_percent": weather_data.get("cloudiness_percent"),
            "visibility_m": weather_data.get("visibility_m"),
        }
    else:
        weather_summary = {"error": weather_data["error"]}

    # Build news summary
    news_alerts = reasoning["news_risk"].get("alerts", [])
    news_summary = {
        "alerts": news_alerts,
        "total_articles_found": news_data.get("total_results", 0),
        "error": news_data.get("error"),
    }
    if not news_summary["error"]:
        del news_summary["error"]

    # Structured report
    report = {
        "location": city,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "weather": weather_summary,
        "news_alerts": news_alerts,
        "event_categories": reasoning.get("event_categories", []),
        "contributing_factors": reasoning["factors"],
        "advice": reasoning["advice"],
        "detail": {
            "weather_risk_score": reasoning["weather_risk"].get("score", 0),
            "news_risk_score": reasoning["news_risk"].get("score", 0),
        },
        "coordinates": {
            "latitude": weather_summary.get("latitude"),
            "longitude": weather_summary.get("longitude"),
        },
    }

    # Human-readable text version
    report["text_report"] = _format_text_report(city, weather_summary, news_alerts, risk_level, risk_score, reasoning["advice"])

    return report


def _format_text_report(
    city: str,
    weather: dict,
    news_alerts: list,
    risk_level: str,
    risk_score: int,
    advice: list,
) -> str:
    """Format the final human-readable CrisisIQ report."""
    RISK_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "UNKNOWN": "⚪"}
    emoji = RISK_EMOJI.get(risk_level, "⚪")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "         🌐 CrisisIQ Report",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 Location: {city}",
        "",
        "🌦️ Weather Conditions:",
    ]

    if "error" in weather:
        lines.append(f"   ⚠️  {weather['error']}")
    else:
        lines.append(f"   • Temperature  : {weather.get('temperature_c', 'N/A')}°C  (Feels like {weather.get('feels_like_c', 'N/A')}°C)")
        lines.append(f"   • Condition    : {weather.get('condition', 'N/A')}")
        lines.append(f"   • Wind Speed   : {weather.get('wind_speed_ms', 'N/A')} m/s")
        lines.append(f"   • Humidity     : {weather.get('humidity_percent', 'N/A')}%")
        lines.append(f"   • Pressure     : {weather.get('pressure_hpa', 'N/A')} hPa")

    lines.append("")
    lines.append("📰 News Alerts:")
    if news_alerts:
        for alert in news_alerts:
            lines.append(f"   • {alert}")
    else:
        lines.append("   • No significant disaster news found.")

    lines += [
        "",
        f"{emoji} Risk Level  : {risk_level}  (Score: {risk_score}/100)",
        "",
        "💡 Safety Advice:",
    ]
    for tip in advice:
        lines.append(f"   {tip}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Main Agent Entry Point
# -----------------------------------------------------------------------------

class CrisisIQAgent:
    """
    ADK-style AI Agent that orchestrates MCP tools and performs
    multi-source reasoning to produce disaster risk intelligence.
    """

    def __init__(self):
        self.name = "CrisisIQ"
        self.version = "1.0.0"
        logger.info(f"[Agent] {self.name} v{self.version} initialized.")

    async def analyze(self, query: str) -> dict:
        """
        Main agent pipeline:
          1. Extract city from query
          2. Run MCP tools (weather + news) in parallel
          3. Reason over combined data
          4. Generate and return structured report

        Args:
            query: Free-form user query string.

        Returns:
            Full CrisisIQ report dict.
        """
        logger.info(f"[Agent] Processing query: '{query}'")

        # Step 1: Extract city
        city = extract_city_from_query(query)
        if not city:
            logger.warning("[Agent] Could not extract city from query.")
            return {
                "error": "Could not identify a city from your query. "
                         "Please specify a city, e.g., 'Is Mumbai at risk today?'"
            }

        logger.info(f"[Agent] Extracted city: {city}")

        # Step 2: Invoke MCP tools
        tool_outputs = await run_mcp_tools(city)
        weather_data = tool_outputs["weather"]
        news_data = tool_outputs["news"]

        # Step 3: Reason
        reasoning = reason_over_data(weather_data, news_data)

        # Step 4: Generate report
        report = generate_report(city, weather_data, news_data, reasoning)

        logger.info(f"[Agent] Report generated. Risk: {report['risk_level']} ({report['risk_score']}/100)")
        return report
