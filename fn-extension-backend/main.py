from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import requests
import os
import hashlib

from ai_core import analyze
from ai_core.schema import AnalysisResult

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str

DE_API_URL = os.getenv("DE_API_URL", "http://localhost:8001")

# Where the pipeline got to before each failure reason stopped it. A run that
# fails at the fetch stage did complete search and filter, and logging it as a
# clean four-step run is what made these failures invisible in production.
_STEPS_BEFORE_FAILURE = {
    "EMPTY_INPUT":         [],
    "NO_SEARCH_RESULTS":   ["search"],
    "NO_CREDIBLE_SOURCES": ["search", "filter"],
    "NO_ARTICLE_CONTENT":  ["search", "filter", "fetch"],
    "LLM_ERROR":           ["search", "filter", "fetch"],
    "PARSE_ERROR":         ["search", "filter", "fetch", "llm"],
}
_ALL_STEPS = ["search", "filter", "fetch", "llm"]


def log_to_de_api(input_text: str, result: AnalysisResult, response_time_ms: int, error_stage: str = None, error_message: str = None):
    """Fire-and-forget logging to the DE API."""
    try:
        input_hash = hashlib.sha256(input_text.encode('utf-8')).hexdigest()

        # A pipeline-internal failure never raises, so it reaches here with
        # error_stage still None. Take it from the result instead.
        failure = result.failure_reason.value if result.failure_reason else None
        if error_stage is None:
            error_stage = failure

        if result.cached:
            steps_completed = ["cache"]
        else:
            steps_completed = _STEPS_BEFORE_FAILURE.get(failure, _ALL_STEPS)

        log_payload = {
            "id": os.urandom(16).hex(), # Unique log ID
            "input_hash": input_hash,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "steps_completed": steps_completed,
            "verdict": result.verdict.value,
            "error_stage": error_stage,
            "error_message": error_message,
            "response_time_ms": response_time_ms
        }
        requests.post(f"{DE_API_URL}/logs", json=log_payload, timeout=2)
    except Exception as e:
        print(f"[backend] Failed to send log to DE API: {e}")

@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(data: AnalyzeRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    print(f"Received: {data.text}")
    
    try:
        # The AI core analyze() handles normalization, cache checks, and full pipeline.
        result = analyze(data.text)
        error_stage = None
        error_message = None
    except Exception as e:
        # Fallback catch-all for orchestration errors
        from ai_core.schema import Verdict, ConfidenceLevel
        result = AnalysisResult(
            verdict=Verdict.NOT_SURE,
            explanation=f"An unexpected error occurred: {str(e)}",
            sources=[],
            confidence=ConfidenceLevel.LOW,
            cached=False
        )
        error_stage = "backend_orchestration"
        error_message = str(e)
        print(f"[backend] Error: {e}")

    response_time_ms = int((time.time() - start_time) * 1000)
    
    # Fire and forget the log
    background_tasks.add_task(log_to_de_api, data.text, result, response_time_ms, error_stage, error_message)
    
    return result

@app.get("/health")
def health():
    return {"status": "ok"}
