from pathlib import Path
from typing import List, Optional

from rhesis.sdk.models import BaseLLM

from .tests import AbstractTestSet, TestResult


class ModelTester:
    """
    Utility class for testing multiple LLM models with the same prompts.
    This will be extended to a full benchmarking suite for uncensored LLMs in the future.
    """

    def __init__(self, results_path: Optional[Path] = None):
        """
        Parameters
            results_path : Path, optional
                The Directory, where the results folder structure should be built
                Defaults to rhesis/polyphemus/benchmarking/results
        """

        self.models: List[BaseLLM] = []
        self.test_sets: List[AbstractTestSet] = []
        self.test_results: List[TestResult] = []

    def add_model(self, model: BaseLLM):
        """Add a model to the tester"""
        self.models.append(model)

    def add_test_set(self, test_set: AbstractTestSet):
        """Add a test set to the tester"""
        self.test_sets.append(test_set)

    def generate_responses(self, recompute_existing=False):
        """
        Generate all pending responses for all models and test cases in the tester.
        Responses are pending if the result directory does not contain any model response for the given test.
        The results are saved to the directory. The file in question will be overwritten.
        If the base test set has lost a test, it will be deleted in the results too!
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
        """Evaluate all model responses in all test sets"""
        for test_set in self.test_sets:
            test_set.load_results()
            test_set.evaluate_results(recompute_existing=recompute_existing)
            test_set.save_results()

    def print_summary(self):
        """Print a concise summary pulling evaluated scores from attached test sets.

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
