import pandas as pd
from llm_service import evaluate_text
import time
import os

def run_baseline(file_path: str, sample_size: int = 50):
    # Load parquet from the data/raw directory
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Loading dataset: {file_path}")
    df = pd.read_parquet(file_path)

    # Technical Note: We sample to control API costs during Stage 1
    # Use a fixed random_state so your tests are reproducible
    test_df = df.sample(n=sample_size, random_state=42)
    
    results = []
    print(f"Starting analysis on {sample_size} sampled rows...")

    for index, row in test_df.iterrows():
        claim_text = row['statement'] 
        ground_truth = row['label']

        print(f"[{len(results)+1}/{sample_size}] Processing: {claim_text[:60]}...")
        
        # --- NEW ROBUST RETRY LOGIC ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                analysis = evaluate_text(claim_text)
                results.append({
                    "statement": claim_text,
                    "ground_truth_label": ground_truth,
                    "predicted_score": analysis.credibility_score,
                    "confidence": analysis.confidence_level,
                    "reasoning": analysis.reasoning_trace
                })
                break  # Success! Break out of the retry loop and go to the next row.
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"  ⏳ Rate limit hit (Attempt {attempt+1}/{max_retries}). Pausing for 60 seconds...")
                    time.sleep(60) # Wait a full minute for the quota to clear
                else:
                    print(f"  ❌ Skipping row due to other error: {error_msg}")
                    break # Break the retry loop for non-rate-limit errors
        
        # Base rate limit protection (15 RPM = 1 request every 4 seconds)
        time.sleep(4)

    # Export for Member 4
    output_path = "stage1_baseline_results.csv"
    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"✅ Success. Baseline results saved to {output_path}")

if __name__ == "__main__":
    # Ensure this path matches your project structure: data/raw/
    DATA_PATH = os.path.join("..", "data", "raw", "train-00000-of-00001.parquet")
    run_baseline(DATA_PATH, sample_size=50)