"""
CrisisIQ - Tools Package Init
Exposes MCP-style tools for weather and news retrieval.
"""

from .weather_tool import fetch_weather, classify_weather_risk
from .news_tool import fetch_disaster_news, classify_news_risk

__all__ = [
    "fetch_weather",
    "classify_weather_risk",
    "fetch_disaster_news",
    "classify_news_risk",
]
