from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_core.schema import AnalysisResult, ConfidenceLevel
from ai_core.prefilter import is_checkable_claim
from ai_core import analyze
from pydantic import BaseModel
app = FastAPI()


origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "chrome-extension://*",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str


@app.get("/")
def read_root():
    return {"Hello": "world"}


@app.get("/health")
def health():
    return {"Service": "is up"}

@app.post("/analyze")
def analyze_endpoint(data: AnalyzeRequest):
    return {
        "verdict": "TRUE",
        "explanation": "According to multiple credible sources, this claim is inaccurate. Reputable outlets have refuted it based on verified data and expert analysis.",
        "sources": [
            {
                "url": "https://vnexpress.net/sample-fact-check",
                "domain": "vnexpress.net",
                "credibility_score": 0.92,
                "title": "Fact check: The truth behind this claim",
                "stance": "CONTRADICTS",
            },
            {
                "url": "https://tuoitre.vn/sample-analysis",
                "domain": "tuoitre.vn",
                "credibility_score": 0.88,
                "title": "Experts weigh in on the controversy",
                "stance": "CONTRADICTS",
            },
        ],
        "confidence": "HIGH",
        "cached": False,
        "response_time_ms": 0,
    }
    
