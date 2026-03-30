"""
CrisisIQ - FastAPI Application Entry Point

Exposes:
  GET  /api/analyze?q=<query> → Full disaster intelligence report
  GET  /health               → Health check
  GET  /                     → Static frontend UI
"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Load .env file automatically (no-op if not present, e.g. in Cloud Run)
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent import CrisisIQAgent, KNOWN_CITIES
from storage import get_profile, save_profile

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------
agent_instance: CrisisIQAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the CrisisIQ agent on startup."""
    global agent_instance
    logger.info("[Startup] Initializing CrisisIQ Agent...")
    agent_instance = CrisisIQAgent()
    logger.info("[Startup] CrisisIQ Agent ready.")
    yield
    logger.info("[Shutdown] CrisisIQ Agent shutting down.")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CrisisIQ – AI Disaster Intelligence Agent",
    description=(
        "An AI agent that analyzes real-time disaster risks "
        "using MCP-integrated weather and news tools."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend/browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST = Path("frontend/dist")
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST)), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """Simple health check endpoint for Cloud Run readiness probes."""
    return {
        "status": "healthy",
        "agent": "CrisisIQ",
        "version": "1.0.0",
    }


@app.get("/api/analyze", tags=["Agent"])
async def analyze(
    q: str = Query(
        ...,
        description="Your disaster risk query, e.g. 'Is Chennai at risk of cyclone today?'",
        min_length=3,
        max_length=300,
    )
):
    """
    Main endpoint: Analyze disaster risk for a given location query.

    The AI agent will:
    1. Extract the city from your query
    2. Fetch real-time weather data (OpenWeatherMap MCP tool)
    3. Fetch disaster news (NewsAPI MCP tool)
    4. Reason over combined data
    5. Return a structured CrisisIQ report

    **Example queries:**
    - `Is Mumbai at risk of flooding?`
    - `Any disaster alerts near Chennai today?`
    - `What is the weather risk in Delhi?`
    """
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent not yet initialized. Please retry.")

    logger.info(f"[API] /api/analyze called with query: '{q}'")

    report = await agent_instance.analyze(q)

    if "error" in report and len(report) == 1:
        raise HTTPException(status_code=400, detail=report["error"])

    return JSONResponse(content=report)


@app.get("/api/cities", tags=["Lookup"])
async def get_city_list():
    """Return the known city list for autocomplete and selection."""
    return JSONResponse(content={"cities": KNOWN_CITIES})


@app.get("/api/profile", tags=["Profile"])
async def get_profile_data(
    user: str = Query("guest", description="Profile username for synced favorites and history."),
):
    profile = get_profile(user)
    return JSONResponse(content={"user": user, **profile})


@app.post("/api/profile", tags=["Profile"])
async def save_profile_data(
    user: str = Query("guest", description="Profile username for synced favorites and history."),
    payload: dict = Body(...),
):
    if not user.strip():
        raise HTTPException(status_code=400, detail="Profile username cannot be empty.")
    profile = save_profile(user, payload)
    return JSONResponse(content={"user": user, **profile})


@app.get("/api/compare", tags=["Agent"])
async def compare_cities(
    cities: str = Query(
        ...,
        description="Comma-separated list of city names to compare risk reports.",
        min_length=1,
    )
):
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent not yet initialized. Please retry.")

    city_list = [city.strip() for city in cities.split(",") if city.strip()]
    if not city_list:
        raise HTTPException(status_code=400, detail="Please provide at least one city to compare.")

    reports = await asyncio.gather(*(agent_instance.analyze(city) for city in city_list))
    return JSONResponse(content={"reports": reports})


@app.get("/{full_path:path}", tags=["UI"])
async def root(full_path: str):
    """Serve the built React frontend for CrisisIQ."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        "<h1>Frontend not built</h1><p>Run <code>npm install</code> and <code>npm run build</code> inside the frontend directory.</p>",
        status_code=503,
    )
