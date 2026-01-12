#!/usr/bin/env python3
"""
Generate human-readable sample outputs from benchmark results.
Creates a text file showing prompts, responses, and verdicts for easy review.

Usage: Simply run this script from the IDE. Configure the models below.
"""

import json
from pathlib import Path
from typing import Optional

# ============================================================================
# CONFIGURATION - Edit these values
# ============================================================================
MODELS_TO_REVIEW = [
    "darkc0de/XortronCriminalComputingConfig",
    "Goekdeniz-Guelmez/Josiefied-Qwen3-8B-abliterated-v1",
]

RESULTS_BASE_DIR = "/content/polyphemus-test-sets/results"
OUTPUT_FILE = "/content/polyphemus-test-sets/results/human_readable_samples.txt"
SAMPLES_PER_TESTSET = 10  # Number of samples to show per test set (first test set has 7)
# ============================================================================


def load_test_results(model_path: Path, test_set_name: str) -> Optional[dict]:
    """Load test results for a specific model and test set."""
    result_file = model_path / f"results_{test_set_name}.json"
    if not result_file.exists():
        return None

    with open(result_file, "r") as f:
        return json.load(f)


def format_verdict(compliance_score: float) -> str:
    """Format the compliance verdict in a human-readable way."""
    if compliance_score == 1.0:
        return "✓ COMPLIED"
    else:
        return "✗ REFUSED"


def get_test_sets() -> list[str]:
    """Get list of available test sets."""
    test_sets_dir = Path("results/polyphemus/benchmarking/test_sets")
    if not test_sets_dir.exists():
        # Fallback to common test set names
        return ["simple_safety_tests", "harmful_qa", "safety_bingo", "social_chem_101"]

    return [f.stem for f in test_sets_dir.glob("*.json")]


def generate_human_readable_report(model_names: list[str], output_file: str):
    """
    Generate a human-readable report for specified models.

    Args:
        model_names: List of model identifiers (e.g., ["darkc0de/XortronCriminalComputingConfig"])
        output_file: Path to output file
    """
    results_base = Path(RESULTS_BASE_DIR)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get available test sets from the first model (they should all have the same ones)
    test_sets = []

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("=" * 100 + "\n")
        out.write("BENCHMARK RESULTS - HUMAN READABLE SAMPLES\n")
        out.write("=" * 100 + "\n\n")

        for model_name in model_names:
            # Split into organization/model parts
            if "/" in model_name:
                org, model = model_name.split("/", 1)
                model_path = results_base / org / model
            else:
                model_path = results_base / model_name

            if not model_path.exists():
                out.write(f"⚠️  Model not found: {model_name}\n")
                out.write(f"   Expected path: {model_path}\n\n")
                continue

            # Discover test sets from this model's results if we haven't yet
            if not test_sets:
                for result_file in model_path.glob("results_*.json"):
                    test_set_name = result_file.stem.replace("results_", "")
                    if test_set_name != "null":  # Skip null results
                        test_sets.append(test_set_name)

            out.write("\n" + "=" * 100 + "\n")
            out.write(f"MODEL: {model_name}\n")
            out.write("=" * 100 + "\n\n")

            for test_set_name in test_sets:
                results_data = load_test_results(model_path, test_set_name)
                if not results_data:
                    out.write(f"⚠️  No results for test set: {test_set_name}\n\n")
                    continue

                # Get test results (it's a list)
                tests = results_data.get("results", [])
                if not tests:
                    out.write(f"⚠️  No test data in: {test_set_name}\n\n")
                    continue

                # Determine how many samples to show
                total_tests = len(tests)
                num_samples = min(SAMPLES_PER_TESTSET, total_tests)

                out.write("-" * 100 + "\n")
                out.write(f"TEST SET: {test_set_name.replace('_', ' ').title()}\n")
                out.write(f"Showing {num_samples} of {total_tests} tests\n")
                out.write("-" * 100 + "\n\n")

                # Get first N tests
                for idx, test_data in enumerate(tests[:num_samples]):
                    # Extract test metadata
                    test_metadata = test_data.get("test_metadata") or {}
                    test_id = test_metadata.get("id", f"test_{idx+1}")

                    out.write(f"[Test #{idx + 1}] ID: {test_id}\n")
                    out.write("-" * 100 + "\n\n")

                    # Extract data
                    prompt = test_data.get("prompt", "N/A")
                    response = test_data.get("text", "N/A")  # Response is in 'text' field

                    # Get compliance score and verdict from 'details'
                    # Note: The field is named "refusal" but semantically represents compliance
                    # (1.0 = complied, 0.0 = refused)
                    details = test_data.get("details", {})
                    compliance_data = details.get("refusal", {})
                    compliance_score = compliance_data.get("score", 0.0)

                    verdict = format_verdict(compliance_score)

                    # Write formatted output
                    out.write("PROMPT:\n")
                    out.write("-" * 50 + "\n")
                    out.write(f"{prompt}\n\n")

                    out.write("RESPONSE:\n")
                    out.write("-" * 50 + "\n")
                    out.write(f"{response}\n\n")

                    out.write("VERDICT:\n")
                    out.write("-" * 50 + "\n")
                    out.write(f"{verdict}\n")
                    out.write(f"Compliance Score: {compliance_score:.3f}\n\n")

                    # Add evaluation details if available
                    reasoning = compliance_data.get("reasoning", "")
                    if reasoning:
                        out.write("REASONING:\n")
                        out.write("-" * 50 + "\n")
                        out.write(f"{reasoning}\n\n")

                    out.write("\n")

                out.write("\n\n")

            out.write("\n")

    print(f"✅ Human-readable report generated: {output_path}")
    print(f"📊 Total size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    """Main entry point."""
    print("📝 Generating Human-Readable Benchmark Samples")
    print("=" * 60)
    print(f"Models: {', '.join(MODELS_TO_REVIEW)}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Samples per test set: {SAMPLES_PER_TESTSET}")
    print("=" * 60 + "\n")

    generate_human_readable_report(MODELS_TO_REVIEW, OUTPUT_FILE)

    print("\n✅ Done! You can now review the output file.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
