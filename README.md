# FireCommand-AI
# FireCommand-AI 🚀
### Autonomous Multi-Agent Wildfire Monitoring & Tactical Dispatch Optimization System

FireCommand-AI is an advanced, production-grade decision-support and automation system designed for fire and rescue services. The platform autonomously ingests real-time satellite fire data, enriches it with multi-source environmental and topographical data, models fire propagation, and optimizes tactical resource allocation using Mixed-Integer Linear Programming (MILP).

---

## 🧠 System Architecture & Multi-Agent Design

The system is built around a **Spatio-Temporal Loop (Master Cycle)** driven by an orchestrated network of specialized, asynchronous AI and Mathematical agents:

* **Ingestion Agent:** Periodically fetches near real-time wildfire hotspots from NASA's FIRMS API (MODIS/VIIRS).
* **Enrichment Agents:** * **Weather Agent (IMS & OWM):** Fetches real-time wind speed, direction, humidity, and temperature.
    * **Topography Agent:** Analyzes slope, elevation, and aspect at the fire coordinates.
    * **Fuel Agent:** Determines fuel type (Forest, Brush, Built Area) and fuel load.
* **Predictor Agent:** Calculates the Rate of Spread (ROS) and flame length, generating geographic prediction polygons (`GeoJSON`).
* **Commander Agent (Optimization Core):** Runs a MILP model via `PuLP` that optimizes resource distribution under hard operational constraints (Suppressing Difficulty Index - SDI).
* **Communications Agent (LLM):** Utilizes **Google Gemini 1.5 Flash** (with a fallback mesh to **Groq/LLaMA 3.3**) to transform raw mathematical dispatch data into clear, human-readable tactical summaries in Hebrew for command centers.

---

## 🛠️ Tech Stack

* **Backend Framework:** Python 3.13, Flask, Flask-SQLAlchemy
* **Real-time Communication:** Flask-SocketIO, WebSockets, gevent
* **Mathematical Optimization:** PuLP (COIN-OR CBC Solver)
* **Geospatial Processing:** Shapely, PyProj, OSRM (Open Source Routing Machine) API
* **AI Orchestration:** Google GenAI SDK, Groq SDK (Cross-Provider Fallback Architecture)
* **Database & Cache:** PostgreSQL (JSONB support), Redis (SocketIO Message Queue)
* **Deployment:** Render (Cloud Production Environment)

---

## 🚀 Getting Started

### Prerequisites
* Python 3.13+
* Homebrew (for macOS geospatial dependencies)
* Redis Server

### Local Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/FireCommand-AI.git](https://github.com/your-username/FireCommand-AI.git)
    cd FireCommand-AI
    ```

2.  **Install system-level geospatial engines (macOS Example):**
    ```bash
    brew install proj
    ```

3.  **Set up Virtual Environment & Install Dependencies:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    PROJ_DIR=/opt/homebrew/opt/proj pip install pyproj==3.6.1
    pip install -r requirements.txt --no-deps
    ```

4.  **Configure Environment Variables (`.env`):**
    Create a `.env` file in the root directory:
    ```env
    DATABASE_URL=postgresql://user:password@localhost:5432/firecommand
    REDIS_URL=redis://localhost:6375
    GEMINI_API_KEY=your_google_ai_studio_key
    GROQ_API_KEY=your_groq_key
    ```

5.  **Run the Applications:**
    * To start the Web/API server:
        ```bash
        python run.py
        ```
    * To start the background automated processing engine (Worker):
        ```bash
        python worker.py
        ```

---

## 📊 Key Architectural Features Showcase

### 🔄 Cross-Provider LLM Fallback Mesh
To guarantee 100% operational uptime without request blocking (Rate Limits), the system features a custom waterfall fallback handler:
1.  **Primary:** Google Gemini 1.5 Flash (Generous free tier, strict JSON schema output via `response_mime_type`).
2.  **Secondary Fallback:** Groq Cloud (`llama-3.3-70b-versatile`).
3.  **Final Fallback:** Groq Cloud (`llama-3.1-8b-instant`).

### ⚡ Massively Parallel Routing (OSRM Table Integration)
Instead of hammering the routing server with $N \times M$ separate HTTP requests for every station-to-fire combination, the `CommanderAgent` aggregates all coordinates into a single batched **OSRM Table API** call, reducing routing calculation time from minutes to milliseconds.
