import os
import json
# NEW SDK IMPORTS
from google import genai
from google.genai import types
from dotenv import load_dotenv

from schema import CredibilityAnalysis 
from prefilter import is_checkable_claim

load_dotenv()

# NEW SDK INITIALIZATION
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
You are the core logic engine for a "Credibility Evaluator" system. 
Your primary task is to analyze user-highlighted text from social media, extract verifiable claims, and assess their factual credibility.

You must think step-by-step to arrive at your conclusion, but your final output MUST be a strictly formatted JSON object.

### INSTRUCTIONS:
1. Identify if the text contains distinct, objectively checkable factual claims.
2. If YES, list the extracted claims. If NO, set `is_factual` false.
3. Assess the credibility of the claims based on general knowledge consensus. 
4. Calculate a `credibility_score` from 0.0 (Completely False/Fabricated) to 1.0 (Completely True/Verified).
5. Determine your `confidence_level` based strictly on these definitions:
   - HIGH: The claim is widely documented, and consensus is clear.
   - MEDIUM: The claim is plausible but lacks definitive consensus.
   - LOW: The claim is highly speculative, extremely recent, or lacks sufficient data.
   - UNVERIFIABLE: The text is an opinion, prediction, or subjective.
6. Write a concise `reasoning_trace` explaining your logic.

### JSON OUTPUT SCHEMA:
{
  "is_factual": boolean,
  "extracted_claims": ["claim 1", "claim 2"],
  "credibility_score": float (0.0 to 1.0),
  "confidence_level": "HIGH" | "MEDIUM" | "LOW" | "UNVERIFIABLE",
  "reasoning_trace": "String explaining your chain of thought step-by-step."
}
"""

def evaluate_text(user_text: str) -> CredibilityAnalysis:
    """
    Takes raw text, runs Layer 1 prefilter, and if it passes, 
    calls Gemini via the NEW SDK to return validated JSON.
    """
    if not is_checkable_claim(user_text):
        return CredibilityAnalysis(
            is_factual=False,
            extracted_claims=[],
            credibility_score=0.5,
            confidence_level="UNVERIFIABLE",
            reasoning_trace="Layer 1 Prefilter: The input does not appear to contain an objectively verifiable claim."
        )

    try:
        # NEW SDK GENERATION CALL
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            )
        )
        
        raw_data = json.loads(response.text)
        validated_data = CredibilityAnalysis(**raw_data)
        return validated_data
        
    except json.JSONDecodeError:
        raise Exception("LLM failed to return valid JSON.")
    except Exception as e:
        raise Exception(f"AI Pipeline Error: {str(e)}")

# --- Verification Block ---
if __name__ == "__main__":
    print("Testing AI Pipeline (V2 SDK)...")
    try:
        test_claim = "The earth is rectangle"
        result = evaluate_text(test_claim)
        print("\n✅ Success! Validated JSON Output:")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"\n❌ Error in pipeline: {e}")