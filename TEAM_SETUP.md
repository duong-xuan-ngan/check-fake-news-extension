# Fake News Detector: Team Setup Guide

This guide will help you get the entire system—including the Chrome Extension Frontend, AI Backend, and Data Engineering API—running on your local machine.

---

## Architecture Overview
*   **Frontend**: Chrome Extension (Sidepanel built with React/Vite).
*   **Backend**: Python FastAPI service (Orchestrates AI analysis).
*   **Data Engineering API**: Python service managing Qdrant (Vector DB) and Postgres (MBFC Credibility Data).

---

## Step 1: Backend Setup (Docker)

1.  **Configure Environment**:
    Copy the example `.env` and fill in your API keys (Gemini/OpenRouter and Serper).
    ```bash
    cp .env.example .env
    ```
2.  **Start Services**:
    Launch the backend infrastructure (Postgres, Qdrant, Redis, Backend, DE-API):
    ```bash
    docker-compose up --build -d
    ```
    *Wait a minute for the databases to initialize and the "Seed" process to complete.*

---

## Step 2: Frontend Setup (Chrome Extension)

The frontend is a React app located in `sidepanel-src` that builds into the `extension/` folder.

1.  **Build the React App**:
    ```bash
    cd sidepanel-src
    npm install
    npm run build
    ```
    *This command compiles the React code and copies it into the `extension/` directory.*

2.  **Load into Chrome**:
    *   Open Chrome and go to `chrome://extensions/`.
    *   Enable **Developer mode** (top right toggle).
    *   Click **Load unpacked** (top left).
    *   Select the **`extension`** folder from the root of this repository.

---

## Step 3: Verifying the Integration

1.  **Run a Test**:
    *   Go to any news website (e.g., BBC, CNN, or a blog).
    *   **Highlight** a claim or a paragraph.
    *   **Right-click** and select "Analyze with Fake News Detector".
    *   The sidepanel should open, show a loading state, and then display the AI analysis.

2.  **Check the Cache**:
    *   Analyze the **same text** a second time.
    *   It should return almost instantly.
    *   Verify by checking the logs:
        ```bash
        docker-compose logs -f backend
        ```
        Look for the message: `[cache] Qdrant Hit!`.

---

## Troubleshooting for Teammates

*   **"Store failed: Object of type datetime is not JSON serializable"**: Fixed. The backend now uses JSON-safe serialization for article dates.
*   **"Qdrant lookup failed"**: Fixed. We updated to the modern `query_points` API. Ensure you ran `docker-compose up --build` to get the latest DE-API image.
*   **Extension not connecting**: Ensure the backend is running at `http://localhost:8000`. Check the browser console (`Inspect` on the sidepanel) for any CORS or connection errors.

---

## Database Access (Optional)
*   **Qdrant UI**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard) (View cached claims).
*   **DE API**: [http://localhost:8001/health](http://localhost:8001/health)
