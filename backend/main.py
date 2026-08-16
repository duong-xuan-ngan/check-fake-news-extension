from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
import hashlib

from pipeline import analyze
from pipeline.schema import AnalysisResult
from app.cache import ensure_collection
from app.config import get_settings
from app.db import write_log
from app.services import credibility_response

_IS_DEV = get_settings().environment == "development"

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

def log_to_de_api(input_text: str, result: AnalysisResult, response_time_ms: int, error_stage: str = None, error_message: str = None):
    """Fire-and-forget logging to the local PostgreSQL repository."""
    try:
        input_hash = hashlib.sha256(input_text.encode('utf-8')).hexdigest()
        log_payload = {
            "id": os.urandom(16).hex(), # Unique log ID
            "input_hash": input_hash,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "steps_completed": ["search", "filter", "fetch", "llm"] if not result.cached else ["cache"],
            "verdict": result.verdict.value,
            "error_stage": error_stage,
            "error_message": error_message,
            "response_time_ms": response_time_ms
        }
        write_log(log_payload)
    except Exception as e:
        print(f"[backend] Failed to write log: {e}")


@app.on_event("startup")
def initialize_cache() -> None:
    ensure_collection()

@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(data: AnalyzeRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    if _IS_DEV:
        print(f"Received: {data.text}")
    
    try:
        # The AI core analyze() handles normalization, cache checks, and full pipeline.
        result = analyze(data.text)
        error_stage = None
        error_message = None
    except Exception as e:
        # Fallback catch-all for orchestration errors
        from pipeline.schema import Verdict, ConfidenceLevel
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


@app.get("/credibility")
def get_credibility(domain: str):
    return credibility_response(domain)


@app.post("/logs")
def create_log(log: dict):
    write_log(log)
    return {"status": "ok"}
