from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_core.schema import AnalysisRequest, CredibilityAnalysis, ConfidenceLevel
from ai_core.prefilter import is_checkable_claim
from ai_core.llm_service import evaluate_text
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
def analyze(data: AnalysisRequest):
    # Access data via attributes
    print(f"Received: {data.text}")
    result = evaluate_text(data.text)
    
    return result
    
