from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_core.schema import AnalysisRequest, CredibilityAnalysis, ConfidenceLevel
from ai_core.prefilter import is_checkable_claim
from ai_core.llm_service import evaluate_text

app = FastAPI()


origins = [
    "http://localhost:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
