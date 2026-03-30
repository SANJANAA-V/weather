# 🌐 CrisisIQ – True AI Disaster Intelligence Agent

> **Real-time disaster risk analysis powered by Google Gemini 2.0 Flash via the Google GenAI SDK, utilizing a True MCP (Model Context Protocol) Server for OpenWeatherMap and NewsAPI.**

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [MCP Explanation](#-what-is-mcp-model-context-protocol)
4. [Project Structure](#-project-structure)
5. [Setup & Local Run](#-setup--local-run)
6. [API Usage](#-api-usage)
7. [Sample Response](#-sample-api-response)
8. [Deployment to Cloud Run](#-deployment-to-google-cloud-run)
9. [Environment Variables](#-environment-variables)

---

## 🎯 Project Overview

**CrisisIQ** is a production-ready AI agent that answers natural-language disaster risk queries like:

- *"Is Chennai at risk of cyclone today?"*
- *"Any disaster alerts near Mumbai?"*
- *"What is the flood risk in Kolkata right now?"*

The agent:
1. **Extracts** the target city from the user query using NLP pattern matching
2. **Invokes MCP tools** (weather + news) in parallel to fetch real-time data
3. **Reasons** over combined signals to classify risk as `LOW`, `MEDIUM`, or `HIGH`
4. **Generates** a structured, human-readable CrisisIQ report with safety advice

---

## 🏗️ Architecture

```
User Query
    │
    ▼
┌───────────────────────────────────────────────────────┐
│              CrisisIQ Agent (Google ADK)              │
│               [gemini-2.0-flash Model]                │
│                                                       │
│  1. Identify user intent via Strict System Prompt     │
│                    │                                  │
│          ┌─────────┴──────────┐                       │
│          │  True MCP Server   │                       │
│          ├────────────────────┤                       │
│  ┌───────▼───────┐  ┌─────────▼──────────┐           │
│  │  Weather Tool │  │     News Tool      │           │
│  │ OpenWeatherMap│  │     NewsAPI        │           │
│  └───────┬───────┘  └─────────┬──────────┘           │
│          └─────────┬──────────┘                       │
│                    │                                  │
│  3. LLM Reasoning (Gemini context window)             │
│     Evaluates weather + news simultaneously           │
│                    │                                  │
│  4. Structured Output Generation (JSON Schema + Text) │
└────────────────────┼──────────────────────────────────┘
                     │
                     ▼
              CrisisIQ Report
         (Risk Level + Score + Advice)
```

### Component Flow

| Step | Component | Description |
|------|-----------|-------------|
| 1 | **Gemini Orchestrator** | Processes queries via `google-genai` using tailored instructions |
| 2a | **Weather MCP Endpoint** | Registered tool for OpenWeatherMap integration |
| 2b | **News MCP Endpoint** | Registered tool for NewsAPI integration |
| 3 | **LLM Reasoning** | Gemini natively interprets data and computes Final Risk Score |
| 4 | **Report Schema** | Guaranteed output format matching the React dashboard UI |

---

## 🔌 What is MCP (Model Context Protocol)?

**MCP (Model Context Protocol)** is a standard for connecting AI agents to external tools and data sources in a structured, interoperable way.

In CrisisIQ, MCP is implemented as:

```
Agent ──invokes──► MCP Tool Contract
                        │
                   ┌────▼────┐
                   │ Input   │  (city: str)
                   │ Schema  │
                   └────┬────┘
                        │
                   ┌────▼────────┐
                   │ External    │  (API call)
                   │ Data Source │
                   └────┬────────┘
                        │
                   ┌────▼────┐
                   │ Output  │  (structured JSON)
                   │ Schema  │
                   └─────────┘
```

Each tool (`weather_tool.py`, `news_tool.py`) follows the MCP pattern:
- **Defined input contract** → city name
- **Defined output contract** → structured Python dict
- **Error handling** built into the tool boundary
- **Composable** → agent can call multiple tools and reason over combined outputs

---

## 📁 Project Structure

```
weather-main/
├── frontend/                # React/Vite UI source + production build
│   ├── dist/               # Built production assets (generated after npm run build)
│   ├── public/             # Optional public assets
│   ├── src/                # React source code
│   ├── package.json        # Frontend dependencies and build scripts
│   └── vite.config.js      # Vite configuration
├── main.py                  # FastAPI app (endpoints + frontend serving)
├── agent.py                 # Core AI agent orchestration via `google-genai`
├── mcp_server.py            # Official MCP implementation registering tools
├── tools/
│   ├── __init__.py          # Package exports
│   ├── weather_tool.py      # OpenWeatherMap API wrapper
│   └── news_tool.py         # NewsAPI wrapper
├── requirements.txt         # Python dependencies
├── Dockerfile               # Production container (frontend + backend)
├── .dockerignore            # Docker build ignore rules
├── .env.example             # Environment variable template
└── README.md                # This file
```

---

## ⚙️ Setup & Local Run

### Prerequisites

- Python 3.10+
- Node 20+ for the React/Vite frontend
- API keys from [OpenWeatherMap](https://openweathermap.org/api) and [NewsAPI](https://newsapi.org/register)

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd weather-main
```

### 2. Backend Dependencies

```bash
pip install -r requirements.txt
```

### 3. Frontend Dependencies & Build

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Your `.env` should look like:

```env
GEMINI_API_KEY=yourgoogleaistudiokey
WEATHER_API_KEY=abc123youropenweathermapkey
NEWS_API_KEY=xyz789yournewsapikey
```

### 5. Run the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Visit [http://localhost:8080](http://localhost:8080) to open the React UI.

### 6. Frontend development

For local frontend development, run the Vite server separately:

```bash
cd frontend
npm run dev -- --host
```

Then visit the URL shown by Vite and keep the backend running separately.

### 7. Run with Docker

Build the container and run it locally:

```bash
docker build -t crisisiq-app .
docker run -p 8080:8080 --env-file .env crisisiq-app
```

Then visit:

```text
http://localhost:8080
```

### 8. Deploy to Google Cloud Run

The repo includes `cloudbuild.yaml` for Cloud Build + Cloud Run deployment.

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _REGION=asia-south1,_SERVICE=crisisiq,_WEATHER_API_KEY=YOUR_KEY,_NEWS_API_KEY=YOUR_KEY
```

After deployment, use the service URL shown by Cloud Run to access the app.

---

## 📡 API Usage

### `GET /api/analyze`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | ✅ | Natural language disaster risk query |

#### Example Requests

```bash
# Basic query
curl "http://localhost:8080/api/analyze?q=Is+Chennai+at+risk+of+cyclone+today"

# Flood risk
curl "http://localhost:8080/api/analyze?q=Any+flood+alerts+near+Mumbai"

# General risk
curl "http://localhost:8080/api/analyze?q=Weather+risk+in+Delhi"
```

### `GET /health`

```bash
curl "http://localhost:8080/health"
# → {"status": "healthy", "agent": "CrisisIQ", "version": "1.0.0"}
```

---

## 📊 Sample API Response

```json
{
  "location": "Chennai",
  "risk_level": "HIGH",
  "risk_score": 72,
  "weather": {
    "temperature_c": 32.4,
    "condition": "Overcast clouds",
    "wind_speed_ms": 18.5,
    "humidity_percent": 88,
    "feels_like_c": 38.1,
    "pressure_hpa": 1008
  },
  "news_alerts": [
    "Cyclone warning issued for coastal Tamil Nadu",
    "IMD puts Chennai on high alert as storm approaches"
  ],
  "contributing_factors": [
    "High wind speed: 18.5 m/s",
    "2 high-severity disaster news article(s) found"
  ],
  "advice": [
    "🚨 Avoid all non-essential travel immediately.",
    "🏠 Stay indoors and away from windows.",
    "📻 Monitor official government and meteorological alerts.",
    "🔦 Prepare an emergency kit (water, food, torch, medicines).",
    "📞 Keep emergency contacts (police: 100, ambulance: 108, NDRF: 1078) handy.",
    "🚫 Do not venture near rivers, coastlines, or low-lying areas.",
    "💨 High wind advisory: secure loose outdoor objects (wind: 18.5 m/s)."
  ],
  "detail": {
    "weather_risk_score": 45,
    "news_risk_score": 40
  },
  "text_report": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n         🌐 CrisisIQ Report\n..."
}
```

---

## ☁️ Deployment to Google Cloud Run

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
- Docker installed and running
- A Google Cloud project with billing enabled

### 1. Authenticate & Set Project

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

### 3. Build & Push Image

```bash
# Build using Cloud Build (no local Docker required)
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/crisisiq
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy crisisiq \
  --image gcr.io/YOUR_PROJECT_ID/crisisiq \
  --platform managed \
  --region asia-south1 \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars WEATHER_API_KEY=your_key_here,NEWS_API_KEY=your_key_here \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5
```

### 5. Get Your Live URL

After deploy, Cloud Run will output a URL:

```
Service URL: https://crisisiq-xxxxxxxx-el.a.run.app
```

Test it:
```bash
curl "https://crisisiq-xxxxxxxx-el.a.run.app/api/analyze?q=Is+Mumbai+safe+today"
```

---

## 🔐 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key for Gemini 2.0 Flash |
| `WEATHER_API_KEY` | ✅ | OpenWeatherMap API key ([get one](https://openweathermap.org/api)) |
| `NEWS_API_KEY` | ✅ | NewsAPI key ([get one](https://newsapi.org/register)) |

> **Security note:** Never hard-code API keys. Use `.env` locally and Cloud Run `--set-env-vars` (or Secret Manager) in production.

---

## 🔢 Risk Scoring Logic

| Source | Weight | Signals |
|--------|--------|---------|
| Weather | 50% | Wind speed, storm conditions, extreme humidity |
| News | 50% | Disaster keyword matches, article volume |

| Final Score | Risk Level | Action |
|-------------|------------|--------|
| 0–24 | 🟢 LOW | Normal conditions |
| 25–59 | 🟡 MEDIUM | Exercise caution |
| 60–100 | 🔴 HIGH | Take immediate action |

---

## 🛠️ Built With

- **FastAPI** – High-performance async Python web framework
- **httpx** – Async HTTP client for MCP tool API calls
- **OpenWeatherMap API** – Real-time weather data
- **NewsAPI** – Real-time disaster news headlines
- **Google Cloud Run** – Serverless container deployment

---

*Built with ❤️ as part of the CrisisIQ AI Agent project.*
