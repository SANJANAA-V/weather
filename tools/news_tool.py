"""
CrisisIQ - News Tool (MCP-style)
Fetches disaster-related news headlines from NewsAPI.
"""

import os
import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"

# Primary disaster keywords for query
DISASTER_KEYWORDS = [
    "cyclone", "hurricane", "typhoon", "tornado",
    "flood", "earthquake", "tsunami", "landslide",
    "storm", "wildfire", "drought", "heatwave",
    "disaster", "emergency alert", "evacuation"
]


async def fetch_disaster_news(city: str, country: Optional[str] = None) -> dict:
    """
    MCP Tool: Fetch recent disaster-related news for a location.

    Args:
        city: City name to search news for.
        country: Optional country name to refine search.

    Returns:
        Structured dict with news articles or error details.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        logger.error("NEWS_API_KEY not set in environment variables.")
        return {"error": "News API key not configured."}

    # Build search query: location + disaster keywords
    location_part = f"{city}"
    if country:
        location_part += f" {country}"

    disaster_query = " OR ".join(DISASTER_KEYWORDS[:6])  # Top 6 keywords to stay within limits
    query = f"({location_part}) AND ({disaster_query})"

    # Fetch news from last 7 days
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NEWSAPI_BASE_URL, params=params)
            response.raise_for_status()
            raw = response.json()

        if raw.get("status") != "ok":
            logger.warning(f"NewsAPI returned non-ok status: {raw.get('status')}")
            return {"error": f"NewsAPI error: {raw.get('message', 'Unknown error')}"}

        articles = raw.get("articles", [])

        # Parse and normalize articles
        parsed_articles = []
        for article in articles:
            title = article.get("title") or ""
            description = article.get("description") or ""

            # Skip removed/deleted articles
            if "[Removed]" in title or not title.strip():
                continue

            parsed_articles.append({
                "title": title.strip(),
                "description": description.strip()[:300] if description else "",
                "source": article.get("source", {}).get("name", "Unknown"),
                "published_at": article.get("publishedAt", ""),
                "url": article.get("url", ""),
            })

        news_data = {
            "city": city,
            "total_results": raw.get("totalResults", 0),
            "articles": parsed_articles,
            "keywords_used": DISASTER_KEYWORDS[:6],
            "fetched_from": from_date,
        }

        logger.info(f"News fetched successfully for city: {city}, articles: {len(parsed_articles)}")
        return news_data

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("Invalid NewsAPI key.")
            return {"error": "Invalid News API key. Please check your NEWS_API_KEY."}
        if e.response.status_code == 429:
            logger.warning("NewsAPI rate limit exceeded.")
            return {"error": "News API rate limit exceeded. Please try again later."}
        logger.error(f"HTTP error fetching news for {city}: {e}")
        return {"error": f"News API returned status {e.response.status_code}."}

    except httpx.RequestError as e:
        logger.error(f"Network error fetching news for {city}: {e}")
        return {"error": "Network error while fetching news data."}

    except Exception as e:
        logger.error(f"Unexpected error in news tool: {e}")
        return {"error": "An unexpected error occurred in the news tool."}


def classify_news_risk(news_data: dict) -> dict:
    """
    Analyze news articles and compute a news-based risk score.

    Risk factors:
      - High-severity disaster keywords in titles → HIGH
      - Moderate-severity keywords → MEDIUM
      - Multiple articles about disaster → increased score

    Returns:
        dict with 'score' (0-100), 'level', 'alerts' list, and 'factors'.
    """
    if "error" in news_data:
        return {"score": 0, "level": "UNKNOWN", "alerts": [], "factors": [news_data["error"]]}

    articles = news_data.get("articles", [])

    HIGH_SEVERITY_KEYWORDS = [
        "cyclone", "hurricane", "typhoon", "tornado", "tsunami",
        "earthquake", "catastrophic", "emergency", "evacuation", "landfall",
        "severe storm", "flash flood", "wildfire"
    ]
    MEDIUM_SEVERITY_KEYWORDS = [
        "flood", "heavy rain", "storm", "warning", "alert",
        "landslide", "heatwave", "drought", "risk", "danger"
    ]

    score = 0
    alerts = []
    factors = []

    high_matches = 0
    medium_matches = 0
    recent_matches = 0

    for article in articles:
        text = (article["title"] + " " + article["description"]).lower()
        matched_high = any(kw in text for kw in HIGH_SEVERITY_KEYWORDS)
        matched_medium = any(kw in text for kw in MEDIUM_SEVERITY_KEYWORDS)

        published_at = article.get("publishedAt") or ""
        is_recent = False
        if published_at:
            try:
                published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                age_hours = (datetime.utcnow().replace(tzinfo=timezone.utc) - published).total_seconds() / 3600
                is_recent = age_hours <= 48
            except ValueError:
                is_recent = False

        if matched_high:
            high_matches += 1
            alerts.append(article["title"])
            if is_recent:
                recent_matches += 1
        elif matched_medium:
            medium_matches += 1
            alerts.append(article["title"])
            if is_recent:
                recent_matches += 1

    # Score based on matches and recency
    if high_matches >= 3:
        score += 60
        factors.append(f"{high_matches} high-severity disaster news articles found")
    elif high_matches >= 1:
        score += 45
        factors.append(f"{high_matches} high-severity disaster news article(s) found")

    if medium_matches >= 3:
        score += 25
        factors.append(f"{medium_matches} moderate disaster news articles found")
    elif medium_matches >= 1:
        score += 12
        factors.append(f"{medium_matches} moderate disaster news article(s) found")

    if recent_matches >= 2:
        score += 15
        factors.append(f"{recent_matches} recent disaster news article(s) (last 48h)")
    elif recent_matches == 1:
        score += 8
        factors.append("Recent disaster news article found (last 48h)")

    if articles and score == 0:
        score += min(10, len(articles) * 2)
        factors.append(f"{len(articles)} disaster-related article(s) found")

    if not articles:
        factors.append("No recent disaster news found for this location")

    score = min(score, 100)

    if score >= 60:
        level = "HIGH"
    elif score >= 20:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "score": score,
        "level": level,
        "alerts": alerts[:5],  # Return top 5 alerts
        "factors": factors,
    }
