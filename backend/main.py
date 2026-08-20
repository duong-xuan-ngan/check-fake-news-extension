from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
import hashlib

from pipeline import analyze
from pipeline.schema import AnalysisResult
from app.auth import (
    get_current_user,
    enforce_daily_quota,
    exchange_google_code,
    issue_tokens,
    rotate_refresh_token,
    revoke_refresh_token,
    GoogleTokenError,
    RefreshTokenError,
)
from app.cache import ensure_collection
from app.config import get_settings
from app.db import write_log, upsert_user, usage_for
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

class GoogleAuthRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str

class RefreshRequest(BaseModel):
    refresh_token: str

def log_to_de_api(input_text: str, result: AnalysisResult, response_time_ms: int, error_stage: str = None, error_message: str = None, user_id: str = None):
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
            "response_time_ms": response_time_ms,
            "user_id": user_id,
        }
        write_log(log_payload)
    except Exception as e:
        print(f"[backend] Failed to write log: {e}")


@app.on_event("startup")
def initialize_cache() -> None:
    ensure_collection()

@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(data: AnalyzeRequest, background_tasks: BackgroundTasks, user: dict = Depends(enforce_daily_quota)):
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
    background_tasks.add_task(log_to_de_api, data.text, result, response_time_ms, error_stage, error_message, user["id"])

    return result

@app.post("/auth/google")
def auth_google(data: GoogleAuthRequest):
    print(f"[auth] /auth/google received code_len={len(data.code)} verifier_len={len(data.code_verifier)} redirect_uri={data.redirect_uri!r}")
    try:
        identity = exchange_google_code(data.code, data.code_verifier, data.redirect_uri)
    except GoogleTokenError as e:
        print(f"[auth] /auth/google FAILED: {e}")
        raise HTTPException(status_code=401, detail=str(e))

    user_id = upsert_user(identity["sub"], identity["email"], identity["name"], identity.get("picture"))
    user = {"id": user_id, "email": identity["email"], "name": identity["name"], "picture": identity.get("picture")}
    print(f"[auth] /auth/google OK user_id={user_id} email={identity['email']}")
    return {**issue_tokens(user_id), "user": user}

@app.post("/auth/refresh")
def auth_refresh(data: RefreshRequest):
    try:
        return rotate_refresh_token(data.refresh_token)
    except RefreshTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/auth/logout")
def auth_logout(data: RefreshRequest):
    revoke_refresh_token(data.refresh_token)
    return {"status": "ok"}

@app.get("/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return {"user": user}


@app.get("/usage")
def get_usage(user: dict = Depends(get_current_user)):
    settings = get_settings()
    today = datetime.now(timezone.utc).date()
    used = usage_for(user["id"], today)
    return {
        "limit": settings.daily_check_limit,
        "used": used,
        "remaining": max(0, settings.daily_check_limit - used),
    }

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
