# `ai_core/` — AI Pipeline Module

Owner: **AI role** (per [`teamrole.md`](../teamrole.md)).
Design source: [`fake_new_detector_brainstorm.md`](../fake_new_detector_brainstorm.md).

## Public contract

Backend calls one function:

```python
from ai_core import evaluate
report = evaluate("highlighted text")  # -> CredibilityReport
```

`CredibilityReport` shape (see [`schema.py`](schema.py)):

```python
{
  "verdict": "TRUE" | "FALSE" | "PARTIALLY_TRUE" | "NOT_SURE",
  "confidence_level": "HIGH" | "MEDIUM" | "LOW" | "UNVERIFIABLE",
  "credibility_score": 0.0..1.0,
  "explanation": "...",
  "sources": [Source, ...],
  "extracted_claims": ["...", ...]
}
```

## Pipeline (v1, sequential)

```
text
 → prefilter.is_checkable_claim    (cheap reject for non-claims)
 → pipeline.query_builder          (text → Serper query)
 → pipeline.searcher               (Serper API → SearchResult[])
 → pipeline.credibility_filter     (DE ratings + CRED-1 risk fallback)
 → pipeline.fetcher                (Newspaper3k → article body)
 → pipeline.analyzer               (Gemini, retrieval-augmented)
 → pipeline.synthesizer            (Verdict + "Not sure" enforcement)
 → CredibilityReport
```

## Module map

| File | Role |
|------|------|
| `__init__.py`               | public `evaluate()` entry point |
| `schema.py`                 | Pydantic models — Source, SearchResult, Verdict, CredibilityReport |
| `prefilter.py`              | regex-based fast reject for non-claims |
| `pipeline/query_builder.py` | text → search query |
| `pipeline/searcher.py`      | Serper API client |
| `pipeline/credibility_filter.py` | DE batch ratings; CRED-1 fallback filters known high-risk domains while retaining unrated evidence |
| `pipeline/fetcher.py`       | Newspaper3k + BeautifulSoup fallback |
| `pipeline/analyzer.py`      | Gemini calls (standalone + RAG) |
| `pipeline/synthesizer.py`   | builds final report; enforces NOT_SURE |
| `evals/batch_eval.py`       | LIAR baseline, standalone path only |

## Status

Implemented:
- `prefilter.is_checkable_claim`
- `pipeline.analyzer.analyze_standalone`
- `evals.batch_eval`

Stubs (raise `NotImplementedError`):
- `query_builder.build_query`
- `searcher.search`
- `credibility_filter.lookup_domain`, `filter_credible`
- `fetcher.fetch`
- `analyzer.analyze_with_evidence`
- `synthesizer.synthesize`

## Environment

Copy `.env.example` → `.env` and fill in keys:

- `GEMINI_API_KEY` — Google AI Studio free tier
- `SERPER_API_KEY` — serper.dev, 2,500 free queries

## Interfaces with other roles

| Direction | What |
|-----------|------|
| Backend → AI | Calls `evaluate(text)` |
| AI → Backend | Returns `CredibilityReport` |
| AI → DE | `credibility_filter` calls DE's `/credibility/batch` endpoint and queues unrated domains for review |
| AI → DE (later) | After v1 lands, hand the verdict to DE's Qdrant store API for caching |

## Running evals

```bash
# from repo root
python -m ai_core.evals.batch_eval
```

Reads `data/raw/train-00000-of-00001.parquet` (LIAR), writes results to
`ai_core/evals/results/stage1_baseline_results.csv`.
