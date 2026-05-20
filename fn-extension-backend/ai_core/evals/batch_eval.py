"""LIAR-dataset baseline: standalone Gemini call, no retrieval.

Usage (from repo root):
    python -m ai_core.evals.batch_eval
"""

import os
import time

import pandas as pd

from ai_core.pipeline.analyzer import analyze_standalone


def run_baseline(file_path: str, sample_size: int = 5):
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Loading dataset: {file_path}")
    df = pd.read_parquet(file_path)
    test_df = df.sample(n=sample_size, random_state=42)

    results = []
    print(f"Starting analysis on {sample_size} sampled rows...")

    for _, row in test_df.iterrows():
        claim_text = row["statement"]
        ground_truth = row["label"]
        print(f"[{len(results)+1}/{sample_size}] Processing: {claim_text[:60]}...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                analysis = analyze_standalone(claim_text)
                results.append({
                    "statement": claim_text,
                    "ground_truth_label": ground_truth,
                    "predicted_score": analysis.credibility_score,
                    "confidence": analysis.confidence_level,
                    "reasoning": analysis.reasoning_trace,
                })
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg:
                    print(f"  Rate limit hit (attempt {attempt+1}/{max_retries}). Pausing 60s...")
                    time.sleep(60)
                else:
                    print(f"  Skipping row due to error: {msg}")
                    break

        time.sleep(4)  # 15 RPM ceiling on Gemini free tier

    output_path = os.path.join(os.path.dirname(__file__), "results", "stage1_baseline_results.csv")
    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"Baseline results saved to {output_path}")


if __name__ == "__main__":
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DATA_PATH = os.path.join(repo_root, "data", "raw", "train-00000-of-00001.parquet")
    run_baseline(DATA_PATH, sample_size=50)
