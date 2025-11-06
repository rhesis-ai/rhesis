"""
Results Curator for Polyphemus Benchmarking

This module provides functionality to curate and analyze all benchmarking results
across multiple test sets and models, generating comprehensive reports.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional


@dataclass
class MetricStatistics:
    """Statistics for a single metric."""

    name: str
    mean: float
    median: float
    std_dev: Optional[float]
    min: float
    max: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": round(self.mean, 4),
            "median": round(self.median, 4),
            "std_dev": round(self.std_dev, 4) if self.std_dev is not None else None,
            "min": round(self.min, 4),
            "max": round(self.max, 4),
            "count": self.count,
        }


@dataclass
class ModelPerformance:
    """Performance data for a single model."""

    model_id: str
    provider: str
    model_name: str

    # Overall metrics
    total_tests: int = 0
    successful_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0

    # Quality metrics
    overall_score: MetricStatistics = None
    metric_scores: Dict[str, MetricStatistics] = field(default_factory=dict)

    # Performance metrics
    cost_heuristic: MetricStatistics = None
    generation_time: MetricStatistics = None
    tokens_in: MetricStatistics = None
    tokens_out: MetricStatistics = None

    # Context usage
    tests_with_context: int = 0
    context_retention_score: Optional[MetricStatistics] = None

    # Refusal analysis
    complied_count: int = 0
    refused_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "model_id": self.model_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "summary": {
                "total_tests": self.total_tests,
                "successful_tests": self.successful_tests,
                "failed_tests": self.failed_tests,
                "error_tests": self.error_tests,
                "success_rate": round(self.successful_tests / self.total_tests * 100, 2)
                if self.total_tests > 0
                else 0,
            },
            "quality_metrics": {
                "overall_score": self.overall_score.to_dict() if self.overall_score else None,
            },
        }

        # Add individual metric scores
        if self.metric_scores:
            for metric_name, stats in self.metric_scores.items():
                result["quality_metrics"][metric_name] = stats.to_dict()

        # Add performance metrics
        result["performance_metrics"] = {}
        if self.cost_heuristic:
            result["performance_metrics"]["cost_heuristic"] = self.cost_heuristic.to_dict()
        if self.generation_time:
            result["performance_metrics"]["generation_time_seconds"] = (
                self.generation_time.to_dict()
            )
        if self.tokens_in:
            result["performance_metrics"]["input_tokens"] = self.tokens_in.to_dict()
        if self.tokens_out:
            result["performance_metrics"]["output_tokens"] = self.tokens_out.to_dict()

        # Add context metrics
        if self.tests_with_context > 0:
            result["context_usage"] = {
                "tests_with_context": self.tests_with_context,
                "context_retention": self.context_retention_score.to_dict()
                if self.context_retention_score
                else None,
            }

        # Add refusal analysis
        if self.complied_count > 0 or self.refused_count > 0:
            result["refusal_analysis"] = {
                "complied": self.complied_count,
                "refused": self.refused_count,
                "compliance_rate": round(
                    self.complied_count / (self.complied_count + self.refused_count) * 100,
                    2,
                ),
            }

        return result


@dataclass
class TestSetSummary:
    """Summary for a single test set."""

    test_set_name: str
    total_tests: int
    models_evaluated: List[str]
    best_overall_model: Optional[str] = None
    best_cost_model: Optional[str] = None
    best_speed_model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_set_name": self.test_set_name,
            "total_tests": self.total_tests,
            "models_evaluated": self.models_evaluated,
            "recommendations": {
                "best_overall_quality": self.best_overall_model,
                "best_cost_efficiency": self.best_cost_model,
                "best_speed": self.best_speed_model,
            },
        }


class ResultsCurator:
    """
    Curates and analyzes all benchmarking results across test sets and models.
    """

    def __init__(self, results_base_path: Path):
        """
        Initialize the curator.

        Parameters
        ----------
        results_base_path : Path
            Base path to the results directory (e.g., results/polyphemus/benchmarking/results)
        """
        self.results_base_path = Path(results_base_path)

        if not self.results_base_path.exists():
            raise ValueError(f"Results path does not exist: {self.results_base_path}")

    def _parse_model_path(self, result_path: Path) -> tuple[str, str]:
        """
        Parse provider and model name from result file path.

        Parameters
        ----------
        result_path : Path
            Path to result file

        Returns
        -------
        tuple[str, str]
            (provider, model_name)
        """
        # Path structure: .../results/{provider}/{model_name}/results_*.json
        parts = result_path.parts
        model_name = parts[-2]
        provider = parts[-3]
        return provider, model_name

    def _compute_statistics(self, values: List[float]) -> MetricStatistics:
        """
        Compute statistics for a list of values.

        Parameters
        ----------
        values : List[float]
            List of numeric values

        Returns
        -------
        MetricStatistics
            Computed statistics
        """
        if not values:
            return None

        return MetricStatistics(
            name="",
            mean=mean(values),
            median=median(values),
            std_dev=stdev(values) if len(values) > 1 else None,
            min=min(values),
            max=max(values),
            count=len(values),
        )

    def _extract_model_data(self, result_files: List[Path]) -> Dict[str, ModelPerformance]:
        """
        Extract and aggregate data for all models from result files.

        Parameters
        ----------
        result_files : List[Path]
            List of result file paths

        Returns
        -------
        Dict[str, ModelPerformance]
            Model ID -> ModelPerformance mapping
        """
        models_data = {}

        for result_file in result_files:
            provider, model_name = self._parse_model_path(result_file)

            with open(result_file, "r") as f:
                data = json.load(f)

            results = data.get("results", [])
            if not results:
                continue

            # Get model ID from first result
            model_id = results[0].get("model_id", f"{provider}/{model_name}")

            if model_id not in models_data:
                models_data[model_id] = ModelPerformance(
                    model_id=model_id,
                    provider=provider,
                    model_name=model_name,
                )

            model_perf = models_data[model_id]

            # Collect all values for statistics
            scores = []
            costs = []
            gen_times = []
            input_tokens = []
            output_tokens = []
            metric_values = {}
            context_retention_values = []

            for result in results:
                model_perf.total_tests += 1

                # Check for errors
                if result.get("error") is not None:
                    model_perf.error_tests += 1
                    continue

                # Check for evaluation
                score = result.get("score")
                if score is None:
                    continue

                if score == 0:
                    model_perf.failed_tests += 1
                else:
                    model_perf.successful_tests += 1

                scores.append(score)

                # Cost
                cost = result.get("cost")
                if cost is not None:
                    costs.append(cost)

                # Metadata
                metadata = result.get("metadata", {})
                if "generation_time_seconds" in metadata:
                    gen_times.append(metadata["generation_time_seconds"])
                if "input_tokens" in metadata:
                    input_tokens.append(metadata["input_tokens"])
                if "output_tokens" in metadata:
                    output_tokens.append(metadata["output_tokens"])

                # Context
                if result.get("context"):
                    model_perf.tests_with_context += 1

                # Metric details
                details = result.get("details", {})
                for metric_name, metric_data in details.items():
                    if not isinstance(metric_data, dict):
                        continue

                    # Handle refusal separately
                    if metric_name == "refusal":
                        verdict = metric_data.get("verdict", "").upper()
                        if verdict == "COMPLIED":
                            model_perf.complied_count += 1
                        elif verdict == "REFUSED":
                            model_perf.refused_count += 1
                        continue

                    # Collect numeric scores
                    metric_score = metric_data.get("score")
                    if metric_score is not None and isinstance(metric_score, (int, float)):
                        if metric_name not in metric_values:
                            metric_values[metric_name] = []
                        metric_values[metric_name].append(metric_score)

                        # Track context retention separately
                        if metric_name == "context_retention":
                            context_retention_values.append(metric_score)

            # Compute statistics
            if scores:
                model_perf.overall_score = self._compute_statistics(scores)
            if costs:
                model_perf.cost_heuristic = self._compute_statistics(costs)
            if gen_times:
                model_perf.generation_time = self._compute_statistics(gen_times)
            if input_tokens:
                model_perf.tokens_in = self._compute_statistics(input_tokens)
            if output_tokens:
                model_perf.tokens_out = self._compute_statistics(output_tokens)
            if context_retention_values:
                model_perf.context_retention_score = self._compute_statistics(
                    context_retention_values
                )

            # Compute per-metric statistics
            for metric_name, values in metric_values.items():
                model_perf.metric_scores[metric_name] = self._compute_statistics(values)
                model_perf.metric_scores[metric_name].name = metric_name

        return models_data

    def _generate_comparisons(self, models_data: Dict[str, ModelPerformance]) -> Dict[str, Any]:
        """
        Generate comparative analysis across models.

        Parameters
        ----------
        models_data : Dict[str, ModelPerformance]
            Model performance data

        Returns
        -------
        Dict[str, Any]
            Comparative analysis
        """
        if not models_data:
            return {}

        # Find best models by different criteria
        best_overall = None
        best_overall_score = -1
        best_cost = None
        best_cost_value = float("inf")
        best_speed = None
        best_speed_value = float("inf")

        for model_id, perf in models_data.items():
            # Best overall quality
            if perf.overall_score and perf.overall_score.mean > best_overall_score:
                best_overall_score = perf.overall_score.mean
                best_overall = model_id

            # Best cost (lowest)
            if perf.cost_heuristic and perf.cost_heuristic.mean < best_cost_value:
                best_cost_value = perf.cost_heuristic.mean
                best_cost = model_id

            # Best speed (lowest generation time)
            if perf.generation_time and perf.generation_time.mean < best_speed_value:
                best_speed_value = perf.generation_time.mean
                best_speed = model_id

        # Quality rankings
        quality_rankings = sorted(
            [
                (model_id, perf.overall_score.mean)
                for model_id, perf in models_data.items()
                if perf.overall_score
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        # Cost rankings
        cost_rankings = sorted(
            [
                (model_id, perf.cost_heuristic.mean)
                for model_id, perf in models_data.items()
                if perf.cost_heuristic
            ],
            key=lambda x: x[1],
        )

        # Speed rankings
        speed_rankings = sorted(
            [
                (model_id, perf.generation_time.mean)
                for model_id, perf in models_data.items()
                if perf.generation_time
            ],
            key=lambda x: x[1],
        )

        # Per-metric comparisons
        metric_rankings = {}
        all_metrics = set()
        for perf in models_data.values():
            all_metrics.update(perf.metric_scores.keys())

        for metric_name in all_metrics:
            rankings = sorted(
                [
                    (model_id, perf.metric_scores[metric_name].mean)
                    for model_id, perf in models_data.items()
                    if metric_name in perf.metric_scores
                ],
                key=lambda x: x[1],
                reverse=True,
            )
            metric_rankings[metric_name] = [
                {"model": model_id, "score": round(score, 4)} for model_id, score in rankings
            ]

        return {
            "best_models": {
                "overall_quality": {
                    "model": best_overall,
                    "score": round(best_overall_score, 4),
                },
                "cost_efficiency": {
                    "model": best_cost,
                    "cost_heuristic": round(best_cost_value, 4),
                },
                "speed": {
                    "model": best_speed,
                    "avg_generation_time_seconds": round(best_speed_value, 4),
                },
            },
            "rankings": {
                "by_overall_quality": [
                    {"model": model_id, "score": round(score, 4)}
                    for model_id, score in quality_rankings
                ],
                "by_cost_efficiency": [
                    {"model": model_id, "cost_heuristic": round(cost, 4)}
                    for model_id, cost in cost_rankings
                ],
                "by_speed": [
                    {
                        "model": model_id,
                        "avg_generation_time_seconds": round(time, 4),
                    }
                    for model_id, time in speed_rankings
                ],
                "by_metric": metric_rankings,
            },
        }

    def _generate_recommendations(
        self, models_data: Dict[str, ModelPerformance], comparisons: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate use-case specific recommendations.

        Parameters
        ----------
        models_data : Dict[str, ModelPerformance]
            Model performance data
        comparisons : Dict[str, Any]
            Comparative analysis

        Returns
        -------
        Dict[str, Any]
            Recommendations
        """
        recommendations = {}

        # General purpose: balance of quality and cost
        quality_cost_scores = []
        for model_id, perf in models_data.items():
            if perf.overall_score and perf.cost_heuristic:
                # Normalize and compute combined score (higher quality, lower cost)
                quality = perf.overall_score.mean
                # Invert cost so lower is better
                cost_score = 1 / (1 + perf.cost_heuristic.mean)
                combined = (quality * 0.6) + (cost_score * 0.4)
                quality_cost_scores.append((model_id, combined, quality, cost_score))

        if quality_cost_scores:
            quality_cost_scores.sort(key=lambda x: x[1], reverse=True)
            best = quality_cost_scores[0]
            recommendations["general_purpose"] = {
                "model": best[0],
                "reason": "Best balance of quality and cost efficiency",
                "quality_score": round(best[2], 4),
                "cost_efficiency_score": round(best[3], 4),
            }

        # High accuracy: best overall quality
        best_quality = comparisons["best_models"]["overall_quality"]
        if best_quality["model"]:
            recommendations["high_accuracy"] = {
                "model": best_quality["model"],
                "reason": "Highest overall quality score",
                "score": best_quality["score"],
            }

        # Budget constrained: best cost
        best_cost = comparisons["best_models"]["cost_efficiency"]
        if best_cost["model"]:
            recommendations["budget_constrained"] = {
                "model": best_cost["model"],
                "reason": "Most cost-efficient option",
                "cost_heuristic": best_cost["cost_heuristic"],
            }

        # Low latency: best speed
        best_speed = comparisons["best_models"]["speed"]
        if best_speed["model"]:
            recommendations["low_latency"] = {
                "model": best_speed["model"],
                "reason": "Fastest generation time",
                "avg_generation_time_seconds": best_speed["avg_generation_time_seconds"],
            }

        # Context-heavy tasks: best context retention
        context_scores = []
        for model_id, perf in models_data.items():
            if perf.context_retention_score:
                context_scores.append((model_id, perf.context_retention_score.mean))

        if context_scores:
            context_scores.sort(key=lambda x: x[1], reverse=True)
            best_context = context_scores[0]
            recommendations["context_heavy_tasks"] = {
                "model": best_context[0],
                "reason": "Best at utilizing and retaining context information",
                "context_retention_score": round(best_context[1], 4),
            }

        # Fluency-critical: best fluency
        if "fluency" in comparisons["rankings"]["by_metric"]:
            best_fluency = comparisons["rankings"]["by_metric"]["fluency"][0]
            recommendations["fluency_critical"] = {
                "model": best_fluency["model"],
                "reason": "Most fluent and natural language generation",
                "fluency_score": best_fluency["score"],
            }

        return recommendations

    def curate_results(self) -> Dict[str, Any]:
        """
        Curate all results and generate comprehensive report.

        Returns
        -------
        Dict[str, Any]
            Complete report data
        """
        # Find all result files
        results_dir = self.results_base_path
        result_files = list(results_dir.glob("**/results_*.json"))

        if not result_files:
            return {
                "error": "No result files found",
                "path_searched": str(results_dir),
            }

        # Extract model data
        models_data = self._extract_model_data(result_files)

        if not models_data:
            return {"error": "No valid model data found in result files"}

        # Generate comparisons
        comparisons = self._generate_comparisons(models_data)

        # Generate recommendations
        recommendations = self._generate_recommendations(models_data, comparisons)

        # Build final report
        report = {
            "metadata": {
                "total_models": len(models_data),
                "total_result_files": len(result_files),
                "results_path": str(results_dir),
            },
            "models": {model_id: perf.to_dict() for model_id, perf in models_data.items()},
            "comparisons": comparisons,
            "recommendations": recommendations,
        }

        return report

    def save_report(self, output_path: Path = None) -> Path:
        """
        Generate and save the curation report to a JSON file.

        Parameters
        ----------
        output_path : Path, optional
            Path to save the report. If None, saves to results_base_path/report.json

        Returns
        -------
        Path
            Path to the saved report
        """
        if output_path is None:
            output_path = self.results_base_path / "report.json"

        report = self.curate_results()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        return output_path
