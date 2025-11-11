import gc
from pathlib import Path
from typing import List, Optional

from rhesis.sdk.models import BaseLLM

from .models.judge import Judge
from .results_curator import ResultsCurator
from .test_sets import TestResult, TestSetEvaluator


class ModelTester:
    """
    Utility class for testing multiple LLM models with the same prompts.
    Handles adding models and test sets, generating responses, evaluating results, and
    summarizing outcomes. Designed for extensibility and future benchmarking needs.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize the ModelTester.

        Parameters
        ----------
        base_dir : Path
            Base directory for benchmarking (e.g., results/polyphemus/benchmarking/).
            Should contain a 'test_sets' subdirectory with test JSON files.
        """
        base_dir = Path(base_dir)
        if not base_dir.exists() or not base_dir.is_dir():
            raise ValueError(f"Invalid base directory: {base_dir}")

        self.base_dir = base_dir
        self.test_sets_dir = base_dir / "test_sets"

        if not self.test_sets_dir.exists() or not self.test_sets_dir.is_dir():
            raise ValueError(f"Test sets directory not found: {self.test_sets_dir}")

        self.models: List[BaseLLM] = []  # Models to be tested
        self.test_sets: List[TestSetEvaluator] = []  # Test sets to use
        for json_file in self.test_sets_dir.glob("*.json"):
            test_set = TestSetEvaluator(json_file)
            self.test_sets.append(test_set)
        self._current_run_results: List[TestResult] = []  # Results from current run

    def add_model(self, model: BaseLLM):
        """
        Add a model to the tester.
        Parameters
        ----------
        model : BaseLLM
            The model to add for benchmarking.
        """
        self.models.append(model)

    def generate(self, recompute_existing=False, print_summary=True):
        """
        Generate responses for all models and test cases.

        This is step 1 of the benchmarking workflow.

        Parameters
        ----------
        recompute_existing : bool, optional
            If True, recompute all responses even if they exist. Default: False.
        print_summary : bool, optional
            If True, print generation summary. Default: True.
        """
        self._current_run_results = []

        for test_set in self.test_sets:
            for model in self.models:
                test_set.add_model(model)
            test_set.load_results()
            if recompute_existing:
                results = test_set.generate_all_responses()
            else:
                results = test_set.generate_pending_responses()
            self._current_run_results.extend(results)

        if print_summary:
            self.print_generation_summary()

    def evaluate(self, recompute_existing=False, print_summary=True):
        """
        Evaluate all model responses in all test sets.

        This is step 2 of the benchmarking workflow.

        Parameters
        ----------
        recompute_existing : bool, optional
            If True, recompute scores even for results that already have scores. Default: False.
        print_summary : bool, optional
            If True, print evaluation summary. Default: True.
        """
        # Load judge model once for all evaluations
        judge = None
        if self.test_sets:
            judge = Judge()
            judge.model, judge.tokenizer, judge.device = judge.load_model()

        try:
            for test_set in self.test_sets:
                test_set.set_judge(judge)
                test_set.load_results()
                test_set.evaluate_results(recompute_existing=recompute_existing)
        finally:
            # Unload judge model
            if judge is not None:
                judge.unload_model()
                del judge
                gc.collect()

        if print_summary:
            self.print_evaluation_summary()

    def print_generation_summary(self):
        """
        Print a summary after generation (before evaluation).
        Shows statistics for newly generated tests and overall status.
        """
        # Get all results (including preexisting)
        all_results: List[TestResult] = []
        for ts in self.test_sets:
            for model_results in getattr(ts, "results", []):
                for r in model_results:
                    if r is not None:
                        all_results.append(r)

        # Get newly generated results
        new_results = self._current_run_results if self._current_run_results else []

        if not all_results and not new_results:
            print("\n=== Generation Summary ===\nNo results found.")
            return

        print("\n=== Generation Summary ===")

        # Overall status (all results including preexisting)
        if all_results:
            total_all = len(all_results)
            successful_all = [r for r in all_results if r.error is None and r.text]
            errors_all = [r for r in all_results if r.error is not None]
            pending_all = [r for r in all_results if r.error is None and r.text and r.score is None]

            print(f"Overall: {total_all} total responses")
            if successful_all:
                success_pct = len(successful_all) / total_all * 100
                print(f"  {len(successful_all)} successful ({success_pct:.1f}%)")
            if errors_all:
                error_pct = len(errors_all) / total_all * 100
                print(f"  {len(errors_all)} errors ({error_pct:.1f}%)")
            if pending_all:
                print(f"  {len(pending_all)} pending evaluation")

        # Newly generated results
        if new_results:
            print(f"\nNewly Generated: {len(new_results)} responses")
            new_successful = [r for r in new_results if r.error is None and r.text]
            new_errors = [r for r in new_results if r.error is not None]

            if len(new_results) > 0:
                if new_successful:
                    new_success_pct = len(new_successful) / len(new_results) * 100
                    print(f"  {len(new_successful)} successful ({new_success_pct:.1f}%)")
                if new_errors:
                    new_error_pct = len(new_errors) / len(new_results) * 100
                    print(f"  {len(new_errors)} errors ({new_error_pct:.1f}%)")

            # Detailed metrics for newly generated only
            if new_successful:
                gen_times = [
                    r.metadata.get("generation_time_seconds", 0)
                    for r in new_successful
                    if r.metadata and "generation_time_seconds" in r.metadata
                ]
                input_tokens = [
                    r.metadata.get("input_tokens", 0)
                    for r in new_successful
                    if r.metadata and "input_tokens" in r.metadata
                ]
                output_tokens = [
                    r.metadata.get("output_tokens", 0)
                    for r in new_successful
                    if r.metadata and "output_tokens" in r.metadata
                ]

                if gen_times:
                    avg_time = sum(gen_times) / len(gen_times)
                    total_time = sum(gen_times)
                    print(f"  Generation time: avg {avg_time:.2f}s, total {total_time:.2f}s")

                if input_tokens and output_tokens:
                    avg_input = sum(input_tokens) / len(input_tokens)
                    avg_output = sum(output_tokens) / len(output_tokens)
                    total_input = sum(input_tokens)
                    total_output = sum(output_tokens)
                    print(
                        f"  Tokens: avg {avg_input:.0f} in / {avg_output:.0f} out, "
                        f"total {total_input} in / {total_output} out"
                    )

            # Per-model breakdown for newly generated
            if len(new_results) > 0:
                per_model = {}
                for r in new_results:
                    mid = r.model_id or "<unknown>"
                    m = per_model.setdefault(
                        mid, {"total": 0, "successful": 0, "errors": 0, "gen_times": []}
                    )
                    m["total"] += 1
                    if r.error is not None:
                        m["errors"] += 1
                    elif r.text:
                        m["successful"] += 1
                        if r.metadata and "generation_time_seconds" in r.metadata:
                            m["gen_times"].append(r.metadata["generation_time_seconds"])

                if len(per_model) > 1:
                    print("\n  Per-model (newly generated):")
                    for mid, s in per_model.items():
                        if s["total"] > 0:
                            model_success_pct = (
                                s["successful"] / s["total"] * 100 if s["total"] > 0 else 0
                            )
                            line = (
                                f"    {mid}: {s['successful']}/{s['total']} "
                                f"successful ({model_success_pct:.1f}%)"
                            )
                            if s["gen_times"]:
                                avg_time = sum(s["gen_times"]) / len(s["gen_times"])
                                line += f", avg {avg_time:.2f}s"
                            if s["errors"] > 0:
                                line += f", {s['errors']} errors"
                            print(line)

            # Show first few errors if any
            if new_errors:
                print("\n  Errors (first 3):")
                for r in new_errors[:3]:
                    error_msg = str(r.error)[:100]
                    print(f"    {r.model_id or '<unknown>'}: {error_msg}")
                if len(new_errors) > 3:
                    print(f"    ... {len(new_errors) - 3} more errors")
        else:
            print("\nNo new responses generated (all tests already had responses)")

        print("\n(Next: Run evaluate() to score pending results)\n")

    def print_evaluation_summary(self):
        """
        Print a detailed summary after evaluation.
        Shows comprehensive metrics for all evaluated results (main focus)
        and brief summary for newly evaluated results.
        """
        # Get all results (including preexisting)
        all_results: List[TestResult] = []
        for ts in self.test_sets:
            for model_results in getattr(ts, "results", []):
                for r in model_results:
                    if r is not None:
                        all_results.append(r)

        # Get newly evaluated results from current run
        new_results = self._current_run_results if self._current_run_results else []

        # Split into evaluated and not evaluated
        all_evaluated = [r for r in all_results if r.error is None and r.score is not None]
        new_evaluated = [r for r in new_results if r.error is None and r.score is not None]

        if not all_evaluated and not new_evaluated:
            print("\n=== Evaluation Summary ===\nNo evaluations found.")
            return

        print("\n=== Evaluation Summary ===")

        # Overall Evaluation (DETAILED - main section)
        if all_evaluated:
            print(f"Overall: {len(all_evaluated)} evaluated responses")

            # Overall quality metrics
            scores = [r.score for r in all_evaluated if r.score is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
                min_score = min(scores)
                max_score = max(scores)
                print(f"  Average Score: {avg_score:.3f} (range: {min_score:.3f}-{max_score:.3f})")

                # Score distribution
                excellent = [s for s in scores if s >= 0.8]
                good = [s for s in scores if 0.6 <= s < 0.8]
                fair = [s for s in scores if 0.4 <= s < 0.6]
                poor = [s for s in scores if s < 0.4]

                excellent_pct = len(excellent) / len(scores) * 100
                good_pct = len(good) / len(scores) * 100
                fair_pct = len(fair) / len(scores) * 100
                poor_pct = len(poor) / len(scores) * 100

                dist_parts = []
                if excellent:
                    dist_parts.append(f"{len(excellent)} excellent ({excellent_pct:.0f}%)")
                if good:
                    dist_parts.append(f"{len(good)} good ({good_pct:.0f}%)")
                if fair:
                    dist_parts.append(f"{len(fair)} fair ({fair_pct:.0f}%)")
                if poor:
                    dist_parts.append(f"{len(poor)} poor ({poor_pct:.0f}%)")

                if dist_parts:
                    print(f"  Distribution: {', '.join(dist_parts)}")

            # Per-model breakdown
            per_model = {}
            for r in all_evaluated:
                mid = r.model_id or "<unknown>"
                if mid not in per_model:
                    per_model[mid] = {"scores": [], "costs": []}
                per_model[mid]["scores"].append(r.score)
                if r.cost is not None:
                    per_model[mid]["costs"].append(r.cost)

            if len(per_model) > 1:
                print("\n  Per-model:")
                sorted_models = sorted(
                    per_model.items(),
                    key=lambda x: sum(x[1]["scores"]) / len(x[1]["scores"]),
                    reverse=True,
                )
                for mid, data in sorted_models:
                    model_avg = sum(data["scores"]) / len(data["scores"])
                    line = f"    {mid}: {model_avg:.3f}"
                    if data["costs"]:
                        model_avg_cost = sum(data["costs"]) / len(data["costs"])
                        line += f" (cost: {model_avg_cost:.4f})"
                    print(line)

        # Newly Evaluated (BRIEF - short summary)
        if new_evaluated:
            print(f"\nNewly Evaluated: {len(new_evaluated)} responses")

            new_scores = [r.score for r in new_evaluated if r.score is not None]
            if new_scores:
                new_avg = sum(new_scores) / len(new_scores)
                print(f"  Average Score: {new_avg:.3f}")

            # Brief per-model summary for newly evaluated
            new_per_model = {}
            for r in new_evaluated:
                mid = r.model_id or "<unknown>"
                if mid not in new_per_model:
                    new_per_model[mid] = []
                new_per_model[mid].append(r.score)

            if len(new_per_model) > 1:
                print("  By Model:")
                for mid, model_scores in sorted(new_per_model.items()):
                    if model_scores:
                        model_avg = sum(model_scores) / len(model_scores)
                        new_model_msg = (
                            f"    {mid}: {model_avg:.3f} ({len(model_scores)} tests)"
                        )
                        print(new_model_msg)
        else:
            print("\nNo new evaluations (all tests already evaluated)")

        print("\n(Next: Run report() for detailed analysis)\n")

    def report(self, output_path: Optional[Path] = None, print_summary=True) -> Path:
        """
        Generate a comprehensive curated report.

        This is step 3 of the benchmarking workflow. Creates a detailed JSON report with:
        - Per-model statistics and metrics
        - Comparative analysis across all models
        - Use-case specific recommendations

        Parameters
        ----------
        output_path : Path, optional
            Path to save the report. If None, saves to "report.json"
        print_summary : bool, optional
            If True, print a summary of the report. Default: True.

        Returns
        -------
        Path
            Path to the generated report

        Example
        -------
        >>> tester = ModelTester(Path("results/polyphemus/benchmarking"))
        >>> tester.add_model(model1)
        >>> tester.generate()
        >>> tester.evaluate()
        >>> report_path = tester.report()
        """
        # Determine results base path
        results_base_path = self.base_dir.joinpath("results")

        curator = ResultsCurator(results_base_path)
        if output_path is None:
            output_path = results_base_path.joinpath("report.json")

        report_path = curator.save_report(output_path)

        if print_summary:
            import json

            with open(report_path) as f:
                report = json.load(f)

            metadata = report.get("metadata", {})
            print(f"\nReport generated: {report_path}")
            print(f"Total models: {metadata.get('total_models', 0)}")
            print(f"Total result files: {metadata.get('total_result_files', 0)}")

            best = report.get("comparisons", {}).get("best_models", {})
            if best.get("overall_quality", {}).get("model"):
                print(f"Best overall: {best['overall_quality']['model']}")
            print()

        return report_path

    def full_run(self, recompute_existing=False):
        """
        Execute the complete benchmarking workflow: generate, evaluate, and report.

        This is a convenience method that runs all three steps in sequence.

        Parameters
        ----------
        recompute_existing : bool, optional
            If True, recompute all responses and scores even if they exist. Default: False.

        Returns
        -------
        Path
            Path to the generated report

        Example
        -------
        >>> tester = ModelTester(Path("results/polyphemus/benchmarking"))
        >>> tester.add_model(model1)
        >>> tester.add_model(model2)
        >>> report_path = tester.full_run()
        """
        print("\n" + "=" * 60)
        print("FULL BENCHMARKING RUN")
        print("=" * 60)

        print("\nStep 1/3: Generating responses...")
        self.generate(recompute_existing=recompute_existing)

        print("\nStep 2/3: Evaluating responses...")
        self.evaluate(recompute_existing=recompute_existing)

        print("\nStep 3/3: Generating report...")
        report_path = self.report()

        print("=" * 60)
        print("BENCHMARKING COMPLETE")
        print("=" * 60)
        print(f"Report: {report_path}\n")

        return report_path
