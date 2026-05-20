# Team Roles & Responsibilities — Fake News Detector

> **Purpose:** This document defines what each role owns, what they receive, and what they return. Use this to assign Trello cards and define interfaces between team members.

---

## System Overview

```
User highlights text
       ↓
   [Frontend]
   Captures text, sends to Backend
       ↓
   [Backend]
   Checks cache (via DE's infrastructure)
       ↓ cache miss
   [AI Pipeline]
   Search → Filter → Fetch → Analyze → Verdict
       ↓
   [Backend]
   Receives verdict, sends back to Frontend
       ↓
   [Frontend]
   Displays result to user
```

---

## 1. Data Engineering (DE)

**Core job:** Build and maintain all data infrastructure that the rest of the system depends on.

### Responsibilities

#### 1.1 Vector Database — Semantic Cache (Qdrant)
- Set up and configure Qdrant as the vector database
- Define the schema for each cached record:
  - `id` — unique record identifier
  - `embedding` — vector representation of the input query
  - `verdict` — credibility level (e.g. True / False / Unverified)
  - `explanation` — LLM-generated explanation
  - `sources` — list of sources with credibility scores
  - `created_at` — timestamp
- Expose a lookup API for Backend to call:
  - Input: query embedding
  - Output: cached record if similarity score ≥ threshold, else null
- Expose a store API for the AI pipeline to call after processing:
  - Input: embedding + verdict + explanation + sources
  - Output: confirmation

#### 1.2 Source Credibility Database (PostgreSQL)
- Set up PostgreSQL for storing source credibility data
- Build and maintain a custom database of Vietnamese news sources and their credibility ratings (supplement MBFC which has limited Vietnamese coverage)
- Fields per record: `domain`, `credibility_score`, `category`, `last_updated`
- Expose a lookup API for the AI pipeline:
  - Input: domain name
  - Output: credibility score and category

#### 1.3 Behavior Data (PostgreSQL)
- Set up a PostgreSQL table to store user behavior data (e.g. which claims were checked, frequency, patterns)
- Purpose: future analysis and model improvement

#### 1.4 Docker Setup
- Containerize the full system so it runs consistently across all environments (dev, staging, production)
- All services (Qdrant, PostgreSQL, Backend, AI Pipeline) should run via Docker Compose

#### 1.5 Logging Infrastructure
- Set up a logging system to record every pipeline run
- Log the following per request:
  - Input text (or hash)
  - Timestamp
  - Pipeline steps completed
  - Final verdict
  - Errors encountered (with step location)
  - Response time per step (for performance monitoring)
- Purpose: debugging errors, monitoring performance, evaluating verdict quality over time

### Interfaces

| Provides to | What |
|-------------|------|
| Backend | Cache lookup API (Qdrant) |
| AI Pipeline | Cache store API (Qdrant) |
| AI Pipeline | Source credibility lookup API (PostgreSQL) |
| All roles | Logging infrastructure |
| All roles | Docker environment |

---

## 2. Backend

**Core job:** Handle all server-side logic — receive requests from Frontend, orchestrate the cache check and AI pipeline, and return results.

### Responsibilities

#### 2.1 API Endpoint
- Expose a REST endpoint that Frontend calls:
  - `POST /analyze`
  - Input: `{ "text": "highlighted text" }`
  - Output: `{ "verdict": "...", "explanation": "...", "sources": [...] }`

#### 2.2 Cache Check (Before Pipeline)
- Before calling the AI pipeline, call DE's cache lookup API
- If cache hit → return cached result immediately to Frontend
- If cache miss → proceed to AI pipeline

#### 2.3 AI Pipeline Orchestration
- Call the AI pipeline with the input text
- Receive verdict, explanation, and sources
- Trigger DE's cache store API to save the result

#### 2.4 API Key Management
- Store and manage all third-party API keys securely as environment variables:
  - Serper API key
  - Gemini API key
  - Any other external service keys
- Never expose keys in code or logs

#### 2.5 Error Handling
- Return meaningful error responses to Frontend if pipeline fails
- Example: `{ "error": "Pipeline failed at search step" }`

### Interfaces

| Receives from | What |
|---------------|------|
| Frontend | Highlighted text via POST /analyze |
| DE | Cache lookup result |
| AI Pipeline | Verdict + explanation + sources |

| Returns to | What |
|------------|------|
| Frontend | Final result or error |
| DE | Data to store in cache |

---

## 3. Frontend (Chrome Extension)

**Core job:** Capture what the user highlights and display the pipeline result — own everything the user sees and interacts with.

### Responsibilities

#### 3.1 Text Highlight Detection
- Detect when a user stops highlighting text on a webpage
- Trigger: `mouseup` event after a non-empty text selection

#### 3.2 Icon Display
- Show a small clickable icon near the highlighted text
- Position it relative to the end of the selection
- Hide it if the user clicks elsewhere

#### 3.3 Request to Backend
- On icon click, send the highlighted text to Backend:
  - `POST /analyze` with `{ "text": "..." }`

#### 3.4 Loading State
- While waiting for Backend response, show a loading indicator inside the panel
- Panel appears immediately on click; result fills in when ready

#### 3.5 Result Display Panel
- Show a two-section panel above/near the highlighted text:
  - **Section 1:** Credibility score + explanation
  - **Section 2:** Sources list with individual credibility ratings
- Handle error state: display a friendly message if Backend returns an error

### Interfaces

| Sends to | What |
|----------|------|
| Backend | Highlighted text via POST /analyze |

| Receives from | What |
|---------------|------|
| Backend | Verdict + explanation + sources (or error) |

---

## Summary Table

| Role | Core Job | Key Trello Cards |
|------|----------|-----------------|
| DE | Data infrastructure | Set up Qdrant, set up PostgreSQL (credibility DB + behavior data), Docker setup, build Vietnamese source credibility DB, set up logging |
| Backend | Server-side logic | Build /analyze endpoint, cache check logic, API key management |
| Frontend | User interface | Highlight detection, icon display, result panel, loading state |
| AI Pipeline (You) | Analysis logic | Search → filter → fetch → analyze → return verdict |

---

*Written after team discussion. To be updated after Backend and Frontend interfaces are finalized.*
