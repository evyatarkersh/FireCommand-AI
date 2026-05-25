# FireCommand-AI 🚀
### Real-Time Wildfire Monitoring & Intelligent Multi-Agent Resource Dispatch System

**Live Dashboard:** 🌐 [firecommand-ai-dash-board.onrender.com](https://firecommand-ai-dash-board.onrender.com/)

---

## 🎯 The Problem & Our Vision

During massive wildfire events, emergency response centers often suffer from **"The Fog of War"**—facing delayed satellite alerts, a complete lack of situational awareness regarding fire propagation, and high-stress environments. Managing multiple concurrent fire incidents leads to chaotic and suboptimal fire-truck dispatch decisions. 

**FireCommand-AI** shifts fire-fighting from a reactive struggle to a proactive, data-driven operation. By automating data digestion and utilizing advanced mathematical dispatch models, the platform manages multiple parallel incidents seamlessly, eliminating human panic and maximizing containment efficiency.

---

## ✨ Key Features

* **Live Global Map Interface:** Displays active real-time wildfire hotspots overlaid with local fire station locations for complete situational awareness.
* **NASA Satellite Integration:** Ingests live thermal anomaly data directly from NASA satellites to identify breakouts as they happen.
* **Visual & Textual Propagation Forecasting:** Calculates and renders dynamic hazard prediction polygons on the map, accompanied by detailed textual summaries of the fire's Rate of Spread (ROS) and risk levels.
* **Multi-Incident Resource Allocation:** Simultaneously monitors multiple fires across regions and automatically resolves resource conflicts, prioritizing high-risk zones without draining critical station reserves.
* **Geospatial ETA Constraints:** The allocation algorithm explicitly accounts for precise travel times (ETA) and Haversine distances from stations to the hot-zones to ensure every dispatch is realistic and optimal.

---

## 🧠 System Architecture & AI Core

The platform is powered by an advanced **Asynchronous Multi-Agent Architecture** integrated with state-of-the-art AI Language Models, driving a continuous strategic cycle:

* **Autonomous Multi-Agent Mesh:** Specialized, independent backend agents collaborate in real time—handling ingestion of NASA streams, enrichment of spatial properties, and wildfire predictive modeling to define containment requirements.
* **Resilient LLM Integration:** Powered by a cross-provider LLM infrastructure featuring a high-availability fallback mesh. The system seamlessly transforms complex mathematical dispatch matrices into clear, structured, and actionable human-readable tactical commands for command centers.
* **Mathematical Optimization Engine:** Formulates a global resource allocation matrix, evaluating available fleets against all active incidents concurrently to deploy the fastest, most effective team configuration.

---

## 🛠️ Tech Stack

* **Frontend:** React, Interactive Map Rendering
* **Backend Framework:** Python 3.13, Flask, Flask-SQLAlchemy
* **Real-time Networking:** Flask-SocketIO, WebSockets
* **AI & Language Architecture:** Multi-Provider LLM Integration (Google Gemini 1.5 Flash & Groq / LLaMA 3.3) & Prompt Orchestration
* **Mathematical Optimization:** Mixed-Integer Linear Programming (MILP) solvers
* **Geospatial Engines:** Shapely, PyProj, OSRM (Open Source Routing Machine) API
* **Cloud Infrastructure:** Render (Live Hosting Environment), Neon (Serverless PostgreSQL Database), Redis Message Queue
