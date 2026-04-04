from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/analyze")
def analyze():
    return {"Analyze": "Mock"}

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    text = request.text
    return {
        "status": "success",
        "result": "This is a mock analysis result.",
    }