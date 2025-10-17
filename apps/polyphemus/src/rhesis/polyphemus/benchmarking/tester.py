from pathlib import Path
from typing import List

from rhesis.sdk.models import BaseLLM

from .test_sets import TestResult, TestSetEvaluator


class ModelTester:
    """
    Utility class for testing multiple LLM models with the same prompts.
    Handles adding models and test sets, generating responses, evaluating results, and summarizing outcomes.
    Designed for extensibility and future benchmarking needs.
    """

    def __init__(self, json_dir: Path):
        """
        Initialize the ModelTester.

        Parameters
        ----------
        results_path : Path, optional
            Directory where the results folder structure should be built.
            Defaults to rhesis/polyphemus/benchmarking/results.
        """
        if not json_dir.exists() or not json_dir.is_dir():
            raise ValueError(f"Invalid test sets directory: {json_dir}")
        
        self.models: List[BaseLLM] = []  # Models to be tested
        self.test_sets: List[TestSetEvaluator] = []  # Test sets to use
        for json_file in json_dir.glob("**/*.json"):
            test_set = TestSetEvaluator(json_file)
            self.test_sets.append(test_set)
        self.test_results: List[TestResult] = []  # Collected test results

    def add_model(self, model: BaseLLM):
        """
        Add a model to the tester.
        Parameters
        ----------
        model : BaseLLM
            The model to add for benchmarking.
        """
        self.models.append(model)

    def generate_responses(self, recompute_existing=False):
        """
        Generate responses for all models and test cases in the tester.
        Responses are generated if not present, or recomputed if requested.
        Results are saved to disk and updated in memory.
        If a test is removed from the base test set, its result is deleted.

        Parameters
        ----------
        recompute_existing : bool
            If True, recompute all responses even if they exist.
        """
        for test_set in self.test_sets:
            for model in self.models:
                test_set.add_model(model)
            test_set.load_results()
            if recompute_existing:
                results = test_set.generate_all_responses(save_results=True)
            else:
                results = test_set.generate_pending_responses(save_results=True)
            self.test_results.extend(results)

    def evaluate_model_responses(self, recompute_existing=False):
        """
        Evaluate all model responses in all test sets.
        Parameters
        ----------
        recompute_existing : bool
            If True, recompute scores even for results that already have scores.
        """
        for test_set in self.test_sets:
            test_set.load_results()
            test_set.evaluate_results(recompute_existing=recompute_existing)
            test_set.save_results()

    def print_summary(self):
        """
        Print a concise summary of evaluated scores from attached test sets.

        Categories:
          pass    -> score > 0
          zero    -> score == 0 (evaluated fail)
          error   -> generation error (error != None)
          pending -> generated (no error) but not yet evaluated (score is None)
        """
        # Prefer the evaluated objects stored inside each test set (they get updated there)
        collected: List[TestResult] = []
        for ts in self.test_sets:
            for model_results in getattr(ts, "results", []):
                for r in model_results:
                    if r is not None:
                        collected.append(r)
        # Fallback to self.test_results if nothing collected (e.g. evaluation not run yet)
        if not collected:
            collected = self.test_results
        # ...existing code...

        if not collected:
            print(
                "\n=== LLM Test Summary ===\nNo results. Run generate_responses() first."
            )
            return

        errors = [r for r in collected if r.error is not None]
        evaluated = [r for r in collected if r.error is None and r.score is not None]
        zero = [r for r in evaluated if (r.score or 0) == 0]
        passed = [r for r in evaluated if (r.score or 0) > 0]
        pending = [r for r in collected if r.error is None and r.score is None]

        scores = [r.score for r in evaluated if r.score is not None]
        avg_score = (sum(scores) / len(scores)) if scores else None

        # Per-model aggregates
        per_model = {}
        for r in collected:
            mid = r.model_id or "<unknown>"
            m = per_model.setdefault(
                mid,
                {
                    "total": 0,
                    "errors": 0,
                    "pending": 0,
                    "zero": 0,
                    "passed": 0,
                    "scores": [],
                },
            )
            m["total"] += 1
            if r.error is not None:
                m["errors"] += 1
            elif r.score is None:
                m["pending"] += 1
            else:
                if r.score == 0:
                    m["zero"] += 1
                elif r.score > 0:
                    m["passed"] += 1
                m["scores"].append(r.score)

        print("\n=== LLM Test Summary ===")
        print(
            f"Total: {len(collected)} | pass: {len(passed)} | zero: {len(zero)} | errors: {len(errors)} | pending: {len(pending)}"
        )
        if avg_score is not None:
            print(f"Avg score: {avg_score:.3f}")

        # Optional timing / token info
        times = [
            r.metadata.get("response_time")
            for r in collected
            if r.metadata and "response_time" in r.metadata
        ]
        tokens = [
            r.metadata.get("tokens_used")
            for r in collected
            if r.metadata and "tokens_used" in r.metadata
        ]
        if times:
            line = f"Avg time: {sum(times) / len(times):.2f}s"
            if tokens:
                line += f" | Tokens: {sum(tokens)}"
            print(line)
        elif tokens:
            print(f"Tokens: {sum(tokens)}")

        if len(per_model) > 1:
            print("Models:")
        for mid, s in per_model.items():
            mscores = s["scores"]
            mavg = sum(mscores) / len(mscores) if mscores else None
            pass_rate = (
                (s["passed"] / (s["passed"] + s["zero"])) * 100
                if (s["passed"] + s["zero"]) > 0
                else 0
            )
            line = f" - {mid}: pass {s['passed']} | zero {s['zero']} | err {s['errors']} | pend {s['pending']}"
            if mavg is not None:
                line += f" | avg {mavg:.3f} | pass% {pass_rate:.1f}"
            print(line)

        if errors:
            print("Errors (first 5):")
            for r in errors[:5]:
                print(f" * {r.model_id or '<unknown>'}: {r.error}")
            if len(errors) > 5:
                print(f"   ... {len(errors) - 5} more")

        if pending and not evaluated:
            print("(Hint: Run evaluate_model_responses() to score pending results.)")
