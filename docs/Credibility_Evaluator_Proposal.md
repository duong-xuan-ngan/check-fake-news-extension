 Credibility Evaluator — Browser Extension
## Technical Proposal v2.0 — Revised & Job-Ready

> **Document version:** 2.0  
> **Status:** Revised for technical soundness & CV impact  
> **Evaluation:** Pre-registered before model development

---

## Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technical Design (AI-Focused)](#3-technical-design-ai-focused)
4. [Implementation Roadmap](#4-implementation-roadmap)
5. [Evaluation Strategy](#5-evaluation-strategy)
6. [Engineering Depth for CV Impact](#6-engineering-depth-for-cv-impact)
7. [Technology Decisions Summary](#7-technology-decisions-summary)
8. [Known Limitations and Future Work](#8-known-limitations-and-future-work)

---

## 1. Project Overview

### 1.1 Problem Statement

Social media platforms distribute content at a scale that exceeds any individual's capacity to verify it. A reader encountering a claim on Facebook or Threads has no efficient mechanism to assess its credibility in context. Fact-checking sites require manual navigation; browser search interrupts reading flow; platform-native labels are coarse, reactive, and opaque.

The gap is not a lack of fact-checking resources. It is **the absence of an ambient, low-friction credibility signal available at the moment of reading** — before the user has already shared or acted on the content.

### 1.2 Objectives

| # | Objective | Measurable Success Criterion |
|---|-----------|------------------------------|
| 1 | Return a credibility score for user-selected text | Score returned in < 3 seconds (P95 latency) |
| 2 | Ground every verdict in external, retrievable sources | ≥ 1 cited source per analysis; no hallucinated citations |
| 3 | Detect rhetorical manipulation patterns | ≥ 4 pattern types flagged (sensationalism, false urgency, appeal to anonymous authority, statistical misuse) |
| 4 | Communicate uncertainty honestly | Claims with weak evidence return an explicit "low confidence" state, not a forced verdict |
| 5 | Explain the score in auditable steps | Reasoning trace and per-dimension breakdown surfaced in UI |
| 6 | Minimise per-query cost | Average API cost < $0.01 using hybrid model routing + caching |

> **Why objective 4 is new and important:** A credibility tool that always produces a confident verdict is more dangerous than one that says "I don't know." Designing the "uncertain" state as a first-class output — not a fallback — is one of the clearest signals of engineering maturity in a trust-critical system.

### 1.3 Scope and Constraints

**In scope:**
- Chrome/Edge extension (Manifest V3)
- Analysis of user-selected text only (not full page DOM)
- Support for Facebook and Threads as primary target platforms
- English-language content at launch
- Backend API accessible over HTTPS

**Out of scope (with rationale):**
- **Full-page passive scanning** — raises privacy concerns; increases cost by an order of magnitude; turns the extension into a surveillance tool
- **Image or video content** — multimodal analysis is a separate engineering problem with separate evaluation requirements
- **Real-time author reputation scoring** — requires authenticated social graph access; introduces significant privacy and legal risk
- **Browser-native ML inference** — model size vs. latency trade-off not yet viable for this use case at acceptable accuracy

**Hard constraints:**
- No user content stored beyond session without explicit opt-in consent
- Analysis must complete within 5 seconds absolute maximum
- Extension must not inject visible UI elements unless the user explicitly triggers analysis

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
+----------------------------------------------------------+
| Browser Extension                                        |
| Content Script -> Background Worker -> Sidebar UI (React)|
+----------------------+-----------------------------------+
                       | HTTPS (JWT-authenticated)
                       v
+----------------------------------------------------------+
| API Gateway (FastAPI)                                    |
| Rate limiting . Request auth . Two-layer cache           |
+----------------------+-----------------------------------+
                       |
                       v
+----------------------------------------------------------+
| Orchestrator (asyncio.gather + timeouts)                 |
| Parallel fan-out . Graceful degradation                  |
+------------+------------------+--------------------------+
             |                  |
             v                  v                  v
+--------------+   +--------------+   +------------------+
| LLM Layer    |   | Retrieval    |   | External APIs    |
| (Haiku/Mini) |   | Pipeline     |   | (ClaimBuster,    |
| Chain-of-    |   | (RAG)        |   | MBFC lookup)     |
| Thought      |   |              |   |                  |
+------+-------+   +------+-------+   +--------+---------+
       |                  |                    |
       +-----------------+--------------------+
                          |
                          v
               +------------------------+
               | Score Synthesiser      |
               | Weighted dimensions .  |
               | Uncertainty flag .     |
               | Reasoning trace        |
               +------------+-----------+
                            |
               +---------------+---------------+
               v               v               v
          PostgreSQL         Redis          Audit log
          (audit log)        (cache)    (URL + timestamp)
```

> **Why `asyncio.gather` instead of Celery:** For three parallel async tasks, Python's built-in `asyncio.gather()` with per-task timeouts provides the same fan-out behaviour as Celery with zero extra infrastructure. Celery is the right tool at production scale — it belongs in the "what I'd do next" section of the README, not in the initial implementation.

### 2.2 Data Flow

```
Step 1  User highlights text on Facebook / Threads
        |-- Content script captures selection + page URL
        |-- No analysis, no storage at this step

Step 2  Background worker hashes text (SHA-256)
        |-- Cache HIT  -> return cached result immediately (< 50ms)
        |-- Cache MISS -> forward to API gateway with JWT

Step 3  API gateway validates token, applies rate limit
        |-- Semantic cache check (embedding cosine > 0.92 threshold)
        |-- Routes to orchestrator on miss

Step 4  Orchestrator fans out in parallel (asyncio.gather):
        |-- Task A: LLM claim extraction + rhetorical pattern analysis
        |-- Task B: RAG retrieval -- web search + vector store
        |-- Task C: External API queries (ClaimBuster, MBFC)

Step 5  Tasks return independently (timeout: 4 seconds total)
        |-- If Task B or C times out -> score synthesiser uses
            available signals and sets confidence = LOW
        |-- Graceful degradation: partial result > no result

Step 6  Score synthesiser computes weighted credibility score
        |-- Sets confidence level: HIGH / MEDIUM / LOW / UNVERIFIABLE
        |-- Generates structured explanation with reasoning trace

Step 7  Response streamed to extension sidebar (SSE)
        |-- Score + confidence badge appear first (< 1s via streaming)
        |-- Per-dimension breakdown and sources render progressively

Step 8  Result written to PostgreSQL audit log
        |-- URL + retrieval timestamp stored (no full source snapshots)
        |-- Redis cache updated (exact-match TTL 24h, semantic TTL 6h)
```

### 2.3 Key Components and Responsibilities

| Component | Single Responsibility | Testable In Isolation? |
|-----------|----------------------|------------------------|
| Content Script | Capture selected text + URL. Nothing else. | Yes — mock selection events |
| Background Worker | Deduplication, cache check, JWT attach, dispatch | Yes — mock API responses |
| API Gateway | Auth, rate limiting, cache lookup, routing | Yes — unit test each middleware layer |
| Orchestrator | Fan-out, timeout, graceful degradation | Yes — inject slow/failing task mocks |
| LLM Analysis Layer | Structured claim extraction + pattern detection | Yes — snapshot test with fixed prompts |
| Retrieval Pipeline | Semantic search + web search, ranked results | Yes — recall@k against known claims |
| Score Synthesiser | Weighted scoring + confidence + reasoning trace | Yes — inject mocked upstream signals |
| Audit Logger | Append-only write to PostgreSQL | Yes — test schema, no reads |

---

## 3. Technical Design (AI-Focused)

### 3.1 Recommended Approach: Three-Layer Hybrid Pipeline

#### Layer 1 — Rule-based pre-filter (< 10ms, zero API cost)

Fast heuristics applied before any API call. Detects obvious non-claims — questions, personal anecdotes, greetings, single-word selections — and routes them to a lightweight "not checkable" response without LLM involvement. Also applies a domain allowlist/blocklist from the source URL.

> **Why this matters:** A system that calls GPT-4 on "Happy birthday!" is not production-ready, regardless of how good the prompt is. This layer demonstrates cost-awareness.

#### Layer 2 — LLM reasoning with structured output (1–3s)

A chain-of-thought prompt instructs the model to:
1. Identify verifiable claims in the selected text
2. Flag rhetorical manipulation patterns
3. Assess the logical structure of the argument
4. Assess whether the claim is verifiable at all (check-worthiness)
5. Return a typed JSON object validated by Pydantic

**Pattern categories detected:**
- Sensational language (superlatives, urgency markers, emotional amplifiers)
- Appeal to anonymous authority ("scientists say", "experts claim" without citation)
- Statistical misuse (percentages without base rates, correlation as causation)
- Absence of evidence markers (vague attribution, unverifiable timeframes)
- False dichotomy or slippery slope framing

#### Layer 3 — Retrieval-augmented grounding (parallel, 2–4s)

The extracted claims are passed to the retrieval pipeline. Each claim triggers a web search and a vector store lookup. Retrieved snippets are ranked by domain authority and recency, then used to ground the LLM's second-pass assessment. This is standard RAG architecture.

### 3.2 Uncertainty as a First-Class Output

| Confidence | Meaning | UI Treatment |
|------------|---------|--------------|
| HIGH | Strong retrieval + LLM agreement | Score displayed normally |
| MEDIUM | Partial retrieval or mild LLM uncertainty | Score with "limited evidence" note |
| LOW | Retrieval failed or conflicting evidence | Score greyed out, warning shown |
| UNVERIFIABLE | Claim is opinion, question, or not factual | "Not a checkable claim" state |

### 3.3 Justification for Chosen Methods

| Design Choice | Why | Trade-off Accepted |
|---------------|-----|--------------------|
| LLM for claim extraction | Claims require semantic understanding, not pattern matching | Latency + cost vs. rule-based |
| RAG for source grounding | Prevents hallucinated citations; provides auditable evidence trail | Retrieval adds latency; can return empty |
| asyncio parallel fan-out | Total latency ≈ slowest task, not sum of tasks | Orchestrator logic is more complex |
| Streaming SSE response | User sees score in < 1s before full explanation loads | Requires SSE support in extension |
| Pydantic output validation | Prevents silent schema drift when model output changes | Prompt must be maintained to produce valid JSON |
| Two-layer cache | Hash-exact for identical text; semantic for rephrased viral claims | Semantic cache threshold requires calibration |
| Small model (Haiku/4o-mini) default | Cost < $0.001 per query for 90%+ of requests | Weaker reasoning on subtle misinformation |
| Large model (Sonnet/GPT-4o) for ambiguous cases | Better reasoning when pre-filter confidence is low | Higher cost, higher latency |

### 3.4 Alternative Approaches Considered and Rejected

**Fine-tuned classifier (DistilBERT on FakeNewsNet)**  
Pros: fast (< 100ms), cheap, local deployment. Cons: brittle on out-of-distribution content; poor explainability; requires labelled data and retraining on domain shift. **Verdict:** use as a pre-filter signal in Layer 1, not as the primary verdict.

**Pure retrieval without LLM (BM25 + source ranking)**  
Pros: deterministic, auditable, no API cost. Cons: cannot reason about claim structure, rhetorical patterns, or context-dependent meaning; no explanation generation. **Verdict:** strong baseline for retrieval evaluation but insufficient as the analysis layer.

**Knowledge graph lookup (Wikidata, DBpedia)**  
Pros: structured entity facts, no hallucination risk. Cons: poor coverage of recent events and social media claims; complex query construction. **Verdict:** document as "future work" for entity-heavy claims.

**Full LangGraph multi-agent orchestration**  
Pros: flexible agent routing, well-documented patterns. Cons: significant debugging overhead for a student team; masks system behaviour behind framework abstractions. **Verdict:** `asyncio.gather` is sufficient for three parallel tasks; LangGraph is correct at production scale.

### 3.5 Explainability Design

Explainability is implemented at three levels:

**Structural:** The score is a weighted sum of named dimensions, each computed independently.

| Dimension | What it measures | Range |
|-----------|-----------------|-------|
| `source_credibility` | Domain authority + media bias indicator of retrieved sources | 0–1 |
| `claim_verifiability` | RAG cross-reference agreement between claim and evidence | 0–1 |
| `rhetorical_integrity` | Severity of detected manipulation patterns | 0–1 |
| `evidence_quality` | Specificity and citability of the original claim | 0–1 |

**Trace:** Chain-of-thought prompting produces a visible reasoning trace per analysis. Stored in the audit log; surfaced in the UI's expandable "How we scored this" panel.

**Source:** Every cited source includes the URL, a domain authority score, a media bias indicator, and the retrieved excerpt.

---

## 4. Implementation Roadmap

### Pre-work — Evaluation Protocol (Before Writing Any Model Code)

1. Download the LIAR dataset. Set aside the official test split — do not touch it until final evaluation.
2. Download 500 claims from FEVER. Set aside 100 as a held-out retrieval evaluation set.
3. Write down in the README, before coding begins: *"We will evaluate on LIAR test split using macro F1, and on FEVER held-out set using Recall@5. A result is 'good enough' if macro F1 > 0.65 and Recall@5 > 0.75."*
4. Commit this file. Any later change to the evaluation criteria must be documented as a deliberate decision.

### 4.1 Stage 1 — MVP (Weeks 1–4)

**Objectives:** Validate the core LLM analysis loop. Deploy a working end-to-end extension.

**Key Features:**
- Chrome extension with text selection capture (Manifest V3)
- FastAPI backend with a single `/analyze` endpoint
- Rule-based pre-filter (Layer 1) — rejects non-claims before LLM call
- Single-prompt LLM analysis with Pydantic-validated JSON output
- Confidence level returned alongside score (all four states from day one)
- Score + confidence badge + plain-English explanation in sidebar
- Exact-match Redis cache

**Technology Stack:**
- Frontend: Chrome Manifest V3, React sidebar
- Backend: Python 3.11, FastAPI, Uvicorn
- AI: Claude Haiku or GPT-4o-mini
- Cache: Redis (Docker locally, Upstash in cloud)
- Deploy: Railway or Render (zero-config, free tier)

**Engineering Focus:** Prompt engineering for reliable structured JSON output; Pydantic schema design and validation logic; retry logic with exponential backoff; baseline evaluation run.

### 4.2 Stage 2 — Retrieval-Augmented Grounding (Weeks 5–9)

**Objectives:** Ground every verdict in retrievable external evidence. Implement and evaluate the RAG pipeline.

**Key Features:**
- Claim extraction as a discrete, independently testable pipeline step
- Web search integration (Brave Search API)
- Vector store for curated source corpus (FAISS locally, Qdrant in cloud)
- Domain authority scoring on retrieved sources
- ClaimBuster API integration for political claim lookup
- Semantic cache layer (embedding similarity threshold = 0.92)
- Confidence level updated based on retrieval quality

**Technology Stack:** LangChain or LlamaIndex; FAISS → Qdrant; `text-embedding-3-small`; Brave Search API; PostgreSQL via Supabase; Redis via Upstash.

**Engineering Focus:** Chunking strategy; retrieval evaluation (Recall@5 on FEVER); semantic cache calibration.

### 4.3 Stage 3 — Multi-Signal Scoring + Full Explainability (Weeks 10–14)

**Key Features:**
- Score decomposed into four named dimensions (`source_credibility`, `claim_verifiability`, `rhetorical_integrity`, `evidence_quality`)
- Configurable dimension weights stored in PostgreSQL — tunable without redeployment
- Confidence level upgraded to reflect multi-signal agreement (HIGH requires ≥ 3 of 4 signals)
- Chain-of-thought reasoning trace stored per analysis in audit log
- UI: expandable "How we scored this" panel with per-dimension breakdown and confidence badge
- Media Bias / Fact Check API integration for source bias labelling
- Ablation comparison: LLM-only vs. retrieval + rules vs. full hybrid

### 4.4 Stage 4 — Evaluation, Polish, and Portfolio Presentation (Weeks 15–18)

**Key Activities:**
- Final evaluation run on LIAR test split
- Error analysis: manually review the 20–30 worst-performing examples; categorise failure modes
- Calibration check: plot ECE — does a score of 70 correspond to ~70% accuracy?
- User feedback collection: thumbs up/down on each verdict; track % "helpful" rating
- Load testing: Locust script to verify P95 latency < 3.5s under concurrent requests
- Clean README with architecture diagram, evaluation results, known limitations, "what I'd do next"

---

## 5. Evaluation Strategy

### 5.1 Pre-Registration

Before any model code is written, commit the following statement to the repository:

> *"We will evaluate the final system on the LIAR official test split using macro F1 as the primary metric. We will evaluate retrieval quality on a 100-claim held-out subset of FEVER using Recall@5. Success is defined as macro F1 > 0.65 and Recall@5 > 0.75. Any deviation from this protocol will be documented as a deliberate decision."*

### 5.2 Metrics

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| Macro F1 | Balance across all credibility classes | > 0.65 on LIAR test split |
| Recall@5 | Correct evidence in top-5 retrieved results | > 0.75 on FEVER held-out |
| ECE (calibration) | Whether confidence scores match actual accuracy | ECE < 0.12 |
| Latency P50 / P95 | User-facing response time | < 1.5s / < 3.5s |
| Cost per query | Average API + infrastructure cost | < $0.01 |
| User helpfulness | % of verdicts rated helpful by user | > 60% |

### 5.3 Datasets

| Dataset | Size | Use | Why This One |
|---------|------|-----|--------------|
| LIAR | 12,800 statements, 6-class | Primary accuracy benchmark | Short political statements; directly matches the social media use case |
| FEVER | 185,000 claims + Wikipedia evidence | Retrieval quality evaluation | Gold-standard evidence sentences enable Recall@k measurement |

Other datasets considered and deferred: FakeNewsNet (article-level, not claim-level), ClaimBuster corpus (check-worthiness only), AVeriTeC (excellent for future work).

### 5.4 Ablation Study

| Configuration | Macro F1 | Notes |
|---------------|----------|-------|
| LLM-only (no retrieval, no rules) | TBD | Baseline: measures LLM contribution alone |
| Rules + retrieval (no LLM verification) | TBD | Measures grounding without reasoning |
| Full hybrid (all three layers) | TBD | Final system |

### 5.5 Error Analysis

After final evaluation, manually review the 20–30 examples the system scored most incorrectly. Categorise each failure:

- **Retrieval failure** — correct claim, wrong/no evidence returned
- **Reasoning failure** — correct evidence retrieved, wrong verdict produced
- **Check-worthiness failure** — claim should not have been scored (opinion flagged as fact)
- **Calibration failure** — verdict correct but confidence level wrong

---

## 6. Engineering Depth for CV Impact

### 6.1 What Separates This From a "Chatbot Wrapper"

| Basic API Wrapper | This System |
|-------------------|-------------|
| Single LLM call, free-text output | Multi-stage pipeline, Pydantic-validated typed output |
| No source citations | RAG with ranked, domain-scored sources |
| Confident verdict always | Four-state confidence with explicit "unverifiable" output |
| No cost control | Rule pre-filter + small/large model routing + two-layer cache |
| No evaluation | Pre-registered benchmark on LIAR and FEVER |
| Single point of failure | Graceful degradation when any service times out |
| Prompt changed ad-hoc | Prompt version ID tracked in audit log alongside scores |
| No observability | Latency, cost, score distribution queryable from PostgreSQL |
| Score unexplained | Per-dimension breakdown + reasoning trace in UI |
| Assumed components are useful | Ablation study proves each component contributes |

### 6.2 The Seven CV Talking Points (With Exact Phrasing)

1. **Pipeline architecture:** "Designed a multi-stage credibility assessment pipeline with independently testable components: rule-based pre-filter, LLM claim extraction, RAG retrieval, and weighted score synthesis."

2. **Structured output engineering:** "Implemented Pydantic schema validation on LLM outputs with retry logic and exponential backoff — preventing silent schema drift across model updates."

3. **RAG with retrieval evaluation:** "Built a retrieval-augmented generation pipeline and measured Recall@5 against a held-out FEVER subset — achieving [X]% before and [Y]% after chunking strategy tuning."

4. **Uncertainty quantification:** "Designed a four-state confidence system (HIGH/MEDIUM/LOW/UNVERIFIABLE) as a first-class output — preventing users from over-relying on low-confidence verdicts."

5. **Ablation study:** "Ran a three-configuration ablation study (LLM-only, retrieval+rules, full hybrid) — demonstrating that retrieval grounding improved macro F1 by [X] points over LLM-only baseline."

6. **Cost and latency architecture:** "Implemented a two-layer cache (hash-exact + semantic similarity) and hybrid model routing (Haiku for 90% of requests, Sonnet for ambiguous cases) — achieving < $0.01 average cost per query."

7. **Pre-registered evaluation:** "Pre-registered the evaluation protocol before model development — locking the test split, metrics, and success criteria to prevent unconscious overfitting to benchmarks."

---

## 7. Technology Decisions Summary

| Component | Technology | Why This, Not the Alternative |
|-----------|-----------|-------------------------------|
| Extension framework | Chrome Manifest V3 | Industry standard; required for Chrome Web Store distribution |
| Backend framework | FastAPI | Async-native; OpenAPI docs auto-generated; Pydantic integration built-in |
| LLM (default) | Claude Haiku / GPT-4o-mini | < $0.001/query; fast; sufficient for structured extraction on clear claims |
| LLM (ambiguous) | Claude Sonnet / GPT-4o | Better reasoning on subtle misinformation; used only when pre-filter confidence is low |
| Embeddings | text-embedding-3-small | Cost-effective; strong semantic similarity; no self-hosting required |
| Vector store | FAISS → Qdrant | FAISS for local dev (zero infrastructure); Qdrant for managed cloud (built-in persistence) |
| Async orchestration | asyncio.gather | Sufficient for 3 parallel tasks; zero extra infrastructure vs. Celery |
| Cache | Redis (Upstash) | Sub-millisecond lookup; TTL support; serverless tier has no cold start |
| Primary DB | PostgreSQL (Supabase) | Structured audit log; SQL queryable; free tier sufficient for a student project |
| Fact-check API | ClaimBuster | Open-source; REST API; strongest political claim coverage of free options |
| Source bias DB | Media Bias / Fact Check | Programmatic API; most comprehensive English-language source bias database |
| Web search | Brave Search API | Privacy-preserving; affordable; no Google Search API dependency |
| Evaluation | scikit-learn + custom harness | Standard metrics with full control; no framework lock-in |
| Deployment | Railway | Zero-config Python deployment; free tier; no Dockerfile required initially |

---

## 8. Known Limitations and Future Work

### Current Limitations

- **Context-dependent claims:** Selected text stripped of conversational context may be misclassified. "This is dangerous" means different things in different threads.
- **English-only:** Rhetorical pattern detection and source quality assessment are calibrated for English-language content.
- **Retrieval coverage:** Viral claims that have not yet generated fact-checked articles will return LOW confidence regardless of actual veracity.
- **Calibration:** The confidence system is manually calibrated; a proper Platt scaling or isotonic regression calibration pass would improve ECE.

### What We Would Do Next (Production System)

- Celery + Redis broker for production-scale async task orchestration
- LoRA fine-tuning on a domain-specific fact-checking dataset, once sufficient labelled examples are collected
- Knowledge distillation: train a DistilBERT classifier on LLM-labelled outputs to reduce cost on high-volume repeat queries
- Local inference path via Ollama for privacy-sensitive deployments (no text leaves the user's machine)
- S3 source snapshots to prevent link rot in the audit log
- Grafana dashboard over the PostgreSQL audit log for production monitoring

---

*Document version 2.0 — revised for technical soundness, scope realism, and CV impact. Primary evaluation datasets pre-registered before model development begins.*
