"""Step 2: turn highlighted text into a Serper search query.

Vague queries return irrelevant results, so we preserve specific details
(numbers, named entities, dates) instead of summarizing.
"""
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"
QUERY_PROMPT = """Your job is to convert highlighted social media text into a search engine query.

Rules:
1. Output the query string only — nothing else  <- you fill this in (output format rule)
2. Keep named entities, numbers, dates verbatim  <- you fill this in (entity preservation rule)  
3. Maximum 15 words, in English  <- you fill this in (length + language rule)
"""

def _extract_entities(text: str) -> str:
    # Match runs of capitalized words (proper nouns) or numbers
    tokens = re.findall(r'\b[A-Z][^\s]*(?:\s+[A-Z][^\s]*)*|\d+', text)
    return " ".join(tokens[:8])  # cap at 8 tokens to stay under 15 words

def build_query(text: str) -> str:
    # Layer 1: clean input
    cleaned = text.strip()  # trim
    cleaned = " ".join(cleaned.split())  # collapse spaces
    cleaned = cleaned[:200]  # truncate to 200 chars

    # Layer 2: LLM reframe, fall back to cleaned if anything goes wrong
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=cleaned,
            config=types.GenerateContentConfig(
                system_instruction=QUERY_PROMPT,
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"[query_builder] LLM call failed: {e}")
    
    # Layer 3: entity extraction fallback
    return _extract_entities(cleaned)
