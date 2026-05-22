"""End-to-end smoke test for the full ai_core.analyze() pipeline.

Runs a small suite of claims (English + Vietnamese, true + false + ambiguous)
through the public analyze() entry point and prints a structured summary for
each. Useful as a quick sanity check after refactors.

Usage (from project root, with venv activated):
    python scripts/test_pipeline.py

    # Run a single case by index:
    python scripts/test_pipeline.py 2

    # Run with a custom claim:
    python scripts/test_pipeline.py --claim "Your custom claim here"
"""
import argparse
import sys
import time
from pathlib import Path

# Make ai_core importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_core import analyze, AnalysisResult


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
# Each case: (description, claim_text, expected_verdict_hint)
# expected_verdict_hint is informational only — pipeline correctness is judged
# by reading the explanation + sources, not by exact string matching.

TEST_CASES = [
    (
        "English / FALSE — wrong club for a real person",
        "Florentino Perez is the president of FC Barcelona",
        "FALSE",
    ),
    (
        "Vietnamese / FALSE — same claim, translated",
        "Florentino Perez là chủ tịch của FC Barcelona",
        "FALSE",
    ),
    (
        "English / TRUE — well-known fact",
        "Paris is the capital of France",
        "TRUE",
    ),
    (
        "English / ambiguous — opinion, not a factual claim",
        "Pineapple belongs on pizza",
        "NOT_SURE or UNVERIFIED",
    ),
]


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------

def _print_separator(char: str = "=", width: int = 80) -> None:
    print(char * width)


def _print_result(result: AnalysisResult, elapsed_seconds: float) -> None:
    print(f"\n  Verdict     : {result.verdict.value}")
    print(f"  Confidence  : {result.confidence.value}")
    print(f"  Cached      : {result.cached}")
    print(f"  Elapsed     : {elapsed_seconds:.2f}s")
    print(f"  Explanation : {result.explanation}")
    print(f"  Sources     : {len(result.sources)}")
    for i, source in enumerate(result.sources, start=1):
        date_str = source.published_at.strftime("%Y-%m-%d") if source.published_at else "no date"
        print(
            f"    [{i}] {source.stance.value:12s} "
            f"(cred={source.credibility_score}, {date_str}) "
            f"{source.domain}"
        )
        print(f"        {source.title[:80]}")


def _run_one(description: str, claim: str, expected_hint: str) -> None:
    _print_separator()
    print(f"CASE: {description}")
    print(f"CLAIM: {claim!r}")
    print(f"EXPECTED HINT: {expected_hint}")
    _print_separator("-")

    # --- Call 1 — should miss cache, run full pipeline ---
    print("\n  [Call 1] running full pipeline...")
    t0 = time.time()
    result1 = analyze(claim)
    elapsed1 = time.time() - t0
    _print_result(result1, elapsed1)

    # --- Call 2 — would hit cache if hashing were deterministic ---
    # (Currently this also misses for non-English claims due to LLM
    # translation jitter — see PROGRESS.md Step 8 note.)
    print("\n  [Call 2] re-running same claim (cache check)...")
    t0 = time.time()
    result2 = analyze(claim)
    elapsed2 = time.time() - t0
    _print_result(result2, elapsed2)

    if result2.cached:
        print(f"\n  ✓ Cache HIT on second call (saved {elapsed1 - elapsed2:.2f}s)")
    else:
        print(f"\n  ✗ Cache MISS on second call (expected for VN input — see PROGRESS.md)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end test for ai_core.analyze()")
    parser.add_argument(
        "index",
        nargs="?",
        type=int,
        default=None,
        help=f"Run a single case by index (0..{len(TEST_CASES) - 1}). Omit to run all.",
    )
    parser.add_argument(
        "--claim",
        type=str,
        default=None,
        help="Run a single custom claim instead of the test suite.",
    )
    args = parser.parse_args()

    if args.claim:
        _run_one("Custom claim from CLI", args.claim, "n/a")
        return

    if args.index is not None:
        if not 0 <= args.index < len(TEST_CASES):
            print(f"Error: index must be 0..{len(TEST_CASES) - 1}")
            sys.exit(1)
        description, claim, expected = TEST_CASES[args.index]
        _run_one(description, claim, expected)
        return

    # Run the whole suite
    print(f"\nRunning {len(TEST_CASES)} test case(s) through ai_core.analyze()...\n")
    for description, claim, expected in TEST_CASES:
        _run_one(description, claim, expected)

    _print_separator()
    print("Done.")


if __name__ == "__main__":
    main()
