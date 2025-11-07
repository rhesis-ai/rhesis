#!/usr/bin/env python3
"""
Dataset Conversion Script for Polyphemus Benchmarking

This script converts various safety/ethics datasets into the Polyphemus test_sets format.
It preserves useful metadata while omitting redundant information like example answers.

Datasets processed:
1. simple_safety_tests.csv - Simple safety prompts with categories
2. harmfull_qa.json - Harmful Q&A with topics and subtopics
3. final_safety_bingo.parquet - Safety prompts with labels
4. social-chem-101 - Social norms and moral judgments (TSV format)

Run once to generate test sets.
"""

import csv
import json
from pathlib import Path

import pandas as pd


def convert_simple_safety_tests(input_path: Path, output_dir: Path, limit: int = None) -> Path:
    """
    Convert simple_safety_tests.csv to test set format.

    Metadata preserved:
    - harm_area: Category of harm (e.g., "Suicide, Self-Harm, and Eating Disorders")
    - category: Type of prompt (e.g., "Information and advice seeking", "Instructions and actions")
    - test_id: Original test ID
    """
    print("Converting simple_safety_tests.csv...")
    tests = []

    with open(input_path, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            test = {
                "prompt": row["prompt"],
                "system_prompt": None,
                "context": None,
                "additional_params": {},
                "expected_text": None,
                "test_metadata": {
                    "test_id": row["id"],
                    "harm_area": row["harm_area"],
                    "category": row["category"],
                    "dataset": "simple_safety_tests",
                },
            }
            tests.append(test)

    output_path = output_dir / "simple_safety_tests.json"
    with open(output_path, "w") as f:
        json.dump({"tests": tests}, f, indent=2)

    print(f"  Created {output_path} with {len(tests)} tests")
    return output_path


def convert_harmful_qa(input_path: Path, output_dir: Path, limit: int = None) -> Path:
    """
    Convert harmfull_qa.json to test set format.

    Metadata preserved:
    - topic: Main topic (e.g., "Social Sciences", "Technology")
    - subtopic: Subtopic (e.g., "Cultural Studies", "Cybersecurity")
    - test_id: Original ID

    Omitted:
    - blue_conversations: Example safe conversations (not needed for testing)
    - red_conversations: Example harmful conversations (not needed for testing)
    """
    print("Converting harmfull_qa.json...")

    with open(input_path, "r") as f:
        data = json.load(f)

    tests = []
    for i, item in enumerate(data):
        if limit and i >= limit:
            break
        test = {
            "prompt": item["question"],
            "system_prompt": None,
            "context": None,
            "additional_params": {},
            "expected_text": None,
            "test_metadata": {
                "test_id": item["id"],
                "topic": item["topic"],
                "subtopic": item["subtopic"],
                "dataset": "harmful_qa",
            },
        }
        tests.append(test)

    output_path = output_dir / "harmful_qa.json"
    with open(output_path, "w") as f:
        json.dump({"tests": tests}, f, indent=2)

    print(f"  Created {output_path} with {len(tests)} tests")
    return output_path


def convert_safety_bingo(input_path: Path, output_dir: Path, limit: int = None) -> Path:
    """
    Convert final_safety_bingo.parquet to test set format.

    Metadata preserved:
    - label: Safety label (e.g., "unsafe\nS5: Hate and discrimination")
    - prompt_label: Prompt-specific label

    Omitted:
    - response: Example responses (not needed for testing)
    """
    print("Converting final_safety_bingo.parquet...")

    df = pd.read_parquet(input_path)
    if limit:
        df = df.head(limit)
    tests = []

    for idx, row in df.iterrows():
        # Parse label to extract category
        label_parts = row["label"].split("\n")
        safety_status = label_parts[0] if len(label_parts) > 0 else "unknown"
        safety_category = label_parts[1] if len(label_parts) > 1 else None

        test = {
            "prompt": row["prompt"],
            "system_prompt": None,
            "context": None,
            "additional_params": {},
            "expected_text": None,
            "test_metadata": {
                "test_id": f"sb_{idx}",
                "safety_status": safety_status,
                "safety_category": safety_category,
                "prompt_label": row["prompt_label"],
                "dataset": "safety_bingo",
            },
        }
        tests.append(test)

    output_path = output_dir / "safety_bingo.json"
    with open(output_path, "w") as f:
        json.dump({"tests": tests}, f, indent=2)

    print(f"  Created {output_path} with {len(tests)} tests")
    return output_path


def convert_social_chem_101(
    input_path: Path, output_dir: Path, sample_size: int = 5000, limit: int = None
) -> Path:
    """
    Convert social-chem-101 TSV to test set format.

    This dataset is very large (140K+ rows), so we sample it.

    Metadata preserved:
    - area: Source area (e.g., "amitheasshole")
    - split: Train/dev/test split
    - rot_categorization: Category of rule-of-thumb
    - rot_moral_foundations: Moral foundation(s)
    - action: The action being judged

    Omitted:
    - rot-agree: Agreement level (not needed)
    - rot-char-targeting: Character targeting (technical detail)
    - rot-bad: Badness indicator (redundant with judgment)
    - rot-judgment: Judgment text (redundant, we test model's judgment)
    - Various other technical fields
    """
    print(f"Converting social-chem-101 (sampling {sample_size} rows)...")

    df = pd.read_csv(input_path, sep="\t")

    # Sample the dataset to make it manageable
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    # Apply limit if in testing mode
    if limit:
        df = df.head(limit)

    tests = []
    for idx, row in df.iterrows():
        # Create a prompt that asks the model to judge the action
        action = row.get("action", "unknown action")
        prompt = f"Is the following action morally acceptable? Action: {action}"

        test = {
            "prompt": prompt,
            "system_prompt": None,
            "context": None,
            "additional_params": {},
            "expected_text": None,
            "test_metadata": {
                "test_id": f"sc101_{idx}",
                "area": row.get("area", "unknown"),
                "split": row.get("split", "unknown"),
                "categorization": row.get("rot-categorization", "unknown"),
                "moral_foundations": row.get("rot-moral-foundations", "unknown"),
                "original_action": action,
                "dataset": "social_chem_101",
            },
        }
        tests.append(test)

    output_path = output_dir / "social_chem_101.json"
    with open(output_path, "w") as f:
        json.dump({"tests": tests}, f, indent=2)

    print(f"  Created {output_path} with {len(tests)} tests")
    return output_path


def main():
    """Main conversion function."""
    limit = None  # Set to an integer for testing with fewer examples

    # Setup paths
    base_dir = Path("results/polyphemus/benchmarking")
    datasets_dir = base_dir / "datasets"
    output_dir = base_dir / "test_sets"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Dataset Conversion Script")
    print("=" * 60)
    print(f"Input directory: {datasets_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Convert each dataset
    created_files = []

    try:
        # 1. Simple safety tests (CSV)
        simple_safety_path = datasets_dir / "simple_safety_tests.csv"
        if simple_safety_path.exists():
            created_files.append(convert_simple_safety_tests(simple_safety_path, output_dir, limit))
        else:
            print(f"Warning: {simple_safety_path} not found, skipping...")

        # 2. Harmful QA (JSON)
        harmful_qa_path = datasets_dir / "harmfull_qa.json"
        if harmful_qa_path.exists():
            created_files.append(convert_harmful_qa(harmful_qa_path, output_dir, limit))
        else:
            print(f"Warning: {harmful_qa_path} not found, skipping...")

        # 3. Safety Bingo (Parquet)
        safety_bingo_path = datasets_dir / "final_safety_bingo.parquet"
        if safety_bingo_path.exists():
            created_files.append(convert_safety_bingo(safety_bingo_path, output_dir, limit))
        else:
            print(f"Warning: {safety_bingo_path} not found, skipping...")

        # 4. Social Chem 101 (TSV)
        social_chem_path = datasets_dir / "social-chem-101/social-chem-101.v1.0.tsv"
        if social_chem_path.exists():
            created_files.append(convert_social_chem_101(social_chem_path, output_dir, limit=limit))
        else:
            print(f"Warning: {social_chem_path} not found, skipping...")

    except Exception as e:
        print(f"\nError during conversion: {e}")
        raise

    print()
    print("=" * 60)
    print("Conversion Complete!")
    print("=" * 60)
    print(f"Created {len(created_files)} test set files:")
    for f in created_files:
        print(f"  - {f.name}")
    print()
    print("You can now run benchmarking with these test sets.")
    print()


if __name__ == "__main__":
    main()
