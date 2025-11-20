#!/usr/bin/env python3
"""
Generate key visualizations from benchmark report for sprint review.
Focus: Model comparison and selection based on benchmark results.
"""

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Configuration
REPORT_PATH = "/content/polyphemus-test-sets/results/report.json"
OUTPUT_DIR = "/content/polyphemus-test-sets/plots"
DPI = 300

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 10


def load_report(report_path):
    """Load the benchmark report."""
    with open(report_path, "r") as f:
        return json.load(f)


def clean_model_name(full_name):
    """Extract clean model name from full model ID, including model size."""
    if "model name: " in full_name:
        name = full_name.split("model name: ")[1]

        # Extract model size using regex (supports 3B, 8B, 24B, 70B, etc.)
        size_match = re.search(r'(\d+\.?\d*[BMK])', name, re.IGNORECASE)
        size_str = f" {size_match.group(1).upper()}" if size_match else ""

        # Handle specific model naming conventions
        if "Josiefied-Qwen3" in name or "Josified-Qwen3" in name:
            return f"Josiefied-Qwen3{size_str}".strip()
        elif "DeepHermes-3" in name or "DeepHermes3" in name:
            return f"DeepHermes 3{size_str}".strip()
        elif "Hermes-3" in name or "Hermes3" in name:
            return f"Hermes 3{size_str}".strip()
        elif "Dolphin" in name or "dphn" in name:
            return f"Dolphin 3.0{size_str}".strip()
        elif "Huihui" in name:
            return f"Huihui-Qwen3-VL{size_str}".strip()
        elif "gemini" in name.lower():
            # Extract version for Gemini models
            if "2.0" in name:
                return "Gemini 2.0 Flash"
            elif "1.5" in name:
                return "Gemini 1.5 Pro" if "pro" in name.lower() else "Gemini 1.5 Flash"
            return "Gemini"

        # Fallback: try to extract a clean name
        if "/" in name:
            parts = name.split("/")
            base_name = parts[1][:30]
            return f"{base_name}{size_str}".strip()
        return name
    return full_name


def plot_overall_ranking(data, output_dir):
    """
    Plot 1: Overall Model Ranking - The Winner
    """
    models = []
    overall_scores = []
    success_rates = []

    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            models.append(clean_model_name(model_id))
            overall_scores.append(model_data["quality_metrics"]["overall_score"]["mean"])
            success_rates.append(model_data["summary"]["success_rate"])

    # Sort by overall score
    sorted_indices = np.argsort(overall_scores)
    models = [models[i] for i in sorted_indices]
    overall_scores = [overall_scores[i] for i in sorted_indices]
    success_rates = [success_rates[i] for i in sorted_indices]

    # Color by performance tier
    colors = []
    for score in overall_scores:
        if score >= 0.75:
            colors.append("#2ecc71")  # Top tier
        elif score >= 0.70:
            colors.append("#3498db")  # Good
        else:
            colors.append("#95a5a6")  # Average

    fig, ax = plt.subplots(figsize=(14, 10))

    y_pos = np.arange(len(models))
    bars = ax.barh(y_pos, overall_scores, color=colors, alpha=0.8)

    # Highlight the winner
    best_idx = len(models) - 1
    bars[best_idx].set_edgecolor("gold")
    bars[best_idx].set_linewidth(3)

    # Add score labels
    for i, score in enumerate(overall_scores):
        ax.text(
            score + 0.01,
            i,
            f"{score:.3f}",
            va="center",
            fontsize=11,
            fontweight="bold" if i == best_idx else "normal",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(models, fontsize=10)
    ax.set_xlabel("Overall Quality Score", fontsize=12, fontweight="bold")
    ax.set_title(
        "🏆 Model Ranking by Overall Quality Score", fontsize=16, fontweight="bold", pad=20
    )
    ax.set_xlim(0.5, max(overall_scores) * 1.15)
    ax.grid(True, alpha=0.3, axis="x")

    # Add legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="#2ecc71", label="Top Tier (≥0.75)"),
        Patch(facecolor="#3498db", label="Good (≥0.70)"),
        Patch(facecolor="#95a5a6", label="Average (<0.70)"),
        Patch(edgecolor="gold", facecolor="none", linewidth=3, label="Best Overall"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / "1_overall_ranking.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 1_overall_ranking.png")
    plt.close()


def plot_safety_quality_tradeoff(data, output_dir):
    """
    Plot 2: Quality vs Compliance - The Key Finding
    Shows which models are both high quality AND compliant (willing to generate content)
    """
    models = []
    overall_scores = []
    compliance_rates = []
    test_counts = []

    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            models.append(clean_model_name(model_id))
            overall_scores.append(model_data["quality_metrics"]["overall_score"]["mean"])
            # Refusal metric is already the compliance rate
            compliance_rates.append(model_data["quality_metrics"]["refusal"]["mean"])
            test_counts.append(model_data["summary"]["total_tests"])

    fig, ax = plt.subplots(figsize=(14, 8))

    # Create scatter plot with size based on number of tests
    sizes = [t * 2 for t in test_counts]
    ax.scatter(
        compliance_rates, overall_scores, s=sizes, alpha=0.6, c=range(len(models)), cmap="tab10"
    )

    # Add model labels
    for i, model in enumerate(models):
        ax.annotate(
            model,
            (compliance_rates[i], overall_scores[i]),
            fontsize=9,
            ha="left",
            va="bottom",
            xytext=(5, 5),
            textcoords="offset points",
        )

    # Add quadrant lines
    ax.axhline(y=np.mean(overall_scores), color="gray", linestyle="--", alpha=0.3, linewidth=1)
    ax.axvline(x=np.mean(compliance_rates), color="gray", linestyle="--", alpha=0.3, linewidth=1)

    # Highlight ideal quadrant (high quality, high compliance)
    ax.fill_between(
        [np.mean(compliance_rates), 1.0],
        np.mean(overall_scores),
        1.0,
        alpha=0.1,
        color="green",
        label="Ideal: High Quality + High Compliance",
    )

    ax.set_xlabel("Compliance Rate (Higher is Better)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Overall Quality Score", fontsize=12, fontweight="bold")
    ax.set_title(
        "Model Quality vs Compliance: The Ideal Models Are in the Top-Right",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )
    ax.legend(loc="lower left")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0.5, 0.85)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "2_selection_matrix.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 2_selection_matrix.png")
    plt.close()


def plot_radar_chart(data, output_dir):
    """
    Plot 3: Top 3 Models - Detailed Metric Comparison
    """
    # Get top 3 models by overall score
    model_scores = []
    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            model_scores.append(
                (
                    clean_model_name(model_id),
                    model_data["quality_metrics"]["overall_score"]["mean"],
                    model_data["quality_metrics"],
                )
            )
    model_scores.sort(key=lambda x: x[1], reverse=True)
    top_3 = model_scores[:3]

    # Metrics to compare
    metrics = ["Fluency", "Relevancy", "Compliance", "Toxicity"]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection="polar"))

    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]  # Complete the circle

    colors = ["#e74c3c", "#3498db", "#2ecc71"]

    for idx, (model_name, overall_score, qm) in enumerate(top_3):
        values = [
            qm["fluency"]["mean"],
            qm["relevancy"]["mean"],
            qm["refusal"]["mean"],  # This is already compliance
            qm["toxicity"]["mean"],  # Higher toxicity is better
        ]
        values += values[:1]  # Complete the circle

        ax.plot(
            angles,
            values,
            "o-",
            linewidth=2,
            label=f"{idx + 1}. {model_name} ({overall_score:.3f})",
            color=colors[idx],
            markersize=8,
        )
        ax.fill(angles, values, alpha=0.15, color=colors[idx])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.grid(True, alpha=0.3)

    ax.set_title(
        "Top 3 Models - Detailed Metric Comparison", fontsize=16, fontweight="bold", pad=30
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / "3_top3_comparison.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 3_top3_comparison.png")
    plt.close()


def plot_model_summary_table(data, output_dir):
    """
    Plot 4: Comprehensive Model Summary
    """
    models_data = []
    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            qm = model_data["quality_metrics"]
            pm = model_data["performance_metrics"]
            summary = model_data["summary"]

            models_data.append(
                {
                    "Model": clean_model_name(model_id),
                    "Overall": f"{qm['overall_score']['mean']:.3f}",
                    "Compliance": f"{qm['refusal']['mean']:.2f}",  # This is already compliance
                    "Fluency": f"{qm['fluency']['mean']:.2f}",
                    "Relevancy": f"{qm['relevancy']['mean']:.2f}",
                    "Toxicity": f"{qm['toxicity']['mean']:.2f}",
                    "Gen Time": f"{pm.get('generation_time_seconds', {}).get('mean', 0):.0f}s"
                    if pm.get("generation_time_seconds")
                    else "N/A",
                    "Tests": f"{summary['total_tests']}",
                }
            )

    # Sort by overall score
    models_data.sort(key=lambda x: float(x["Overall"]), reverse=True)

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.axis("tight")
    ax.axis("off")

    # Create table
    table_data = [
        [
            m[k]
            for k in [
                "Model",
                "Overall",
                "Compliance",
                "Fluency",
                "Relevancy",
                "Toxicity",
                "Gen Time",
                "Tests",
            ]
        ]
        for m in models_data
    ]
    headers = [
        "Model",
        "Overall\nScore",
        "Compliance",
        "Fluency",
        "Relevancy",
        "Toxicity",
        "Avg Gen\nTime",
        "Tests",
    ]

    table = ax.table(
        cellText=table_data, colLabels=headers, cellLoc="center", loc="center", bbox=[0, 0, 1, 1]
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.5)

    # Style header
    for i in range(len(headers)):
        cell = table[(0, i)]
        cell.set_facecolor("#3498db")
        cell.set_text_props(weight="bold", color="white", fontsize=11)

    # Style rows
    for i in range(len(models_data)):
        # Highlight top 3
        if i < 3:
            bg_color = ["#ffeaa7", "#dfe6e9", "#fab1a0"][i]
        else:
            bg_color = "#ecf0f1" if i % 2 == 0 else "white"

        for j in range(len(headers)):
            cell = table[(i + 1, j)]
            cell.set_facecolor(bg_color)

            # Bold the model name column
            if j == 0:
                cell.set_text_props(weight="bold", ha="left")

            # Highlight best overall score
            if j == 1 and i == 0:
                cell.set_text_props(weight="bold", color="#2ecc71")

    ax.set_title("Comprehensive Model Comparison Summary", fontsize=16, fontweight="bold", pad=20)

    plt.tight_layout()
    plt.savefig(output_dir / "4_summary_table.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 4_summary_table.png")
    plt.close()


def plot_metric_breakdown(data, output_dir):
    """
    Plot 5: Detailed Metric Breakdown - Bar Chart
    Shows all key metrics side by side for easy comparison
    """
    models = []
    metrics_data = {"Fluency": [], "Relevancy": [], "Compliance": [], "Toxicity": []}

    for model_id, model_data in data["models"].items():
        qm = model_data["quality_metrics"]
        if qm["overall_score"]:
            models.append(clean_model_name(model_id))
            metrics_data["Fluency"].append(qm["fluency"]["mean"])
            metrics_data["Relevancy"].append(qm["relevancy"]["mean"])
            metrics_data["Compliance"].append(qm["refusal"]["mean"])  # This is already compliance
            metrics_data["Toxicity"].append(qm["toxicity"]["mean"])  # Higher is better

    # Sort by overall quality
    overall_scores = [
        data["models"][mid]["quality_metrics"]["overall_score"]["mean"]
        for mid in data["models"].keys()
        if data["models"][mid]["quality_metrics"]["overall_score"]
    ]
    sorted_indices = np.argsort(overall_scores)[::-1]

    models = [models[i] for i in sorted_indices]
    for key in metrics_data:
        metrics_data[key] = [metrics_data[key][i] for i in sorted_indices]

    # Create grouped bar chart
    x = np.arange(len(models))
    width = 0.2

    fig, ax = plt.subplots(figsize=(16, 8))

    colors = ["#2ecc71", "#3498db", "#e74c3c", "#f39c12"]
    positions = [x - 1.5 * width, x - 0.5 * width, x + 0.5 * width, x + 1.5 * width]

    for i, (metric, color, pos) in enumerate(zip(metrics_data.keys(), colors, positions)):
        ax.bar(pos, metrics_data[metric], width, label=metric, color=color, alpha=0.8)

    ax.set_xlabel("Models (Sorted by Overall Quality)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Score (0-1)", fontsize=12, fontweight="bold")
    ax.set_title("Detailed Metric Breakdown by Model", fontsize=14, fontweight="bold", pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=45, ha="right", fontsize=9)
    ax.legend(loc="lower left", fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(output_dir / "5_metric_breakdown.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 5_metric_breakdown.png")
    plt.close()


def plot_compliance_focus(data, output_dir):
    """
    Plot 6: Compliance Rate Focus
    Highlights the compliance metric with error bars
    """
    models = []
    compliance_means = []
    compliance_stds = []
    colors = []

    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            models.append(clean_model_name(model_id))
            refusal_data = model_data["quality_metrics"]["refusal"]
            # This is already compliance
            compliance_mean = refusal_data["mean"]
            compliance_means.append(compliance_mean)
            compliance_stds.append(refusal_data.get("std_dev", 0))
            # Color by compliance level
            if compliance_mean > 0.9:
                colors.append("#2ecc71")  # Green - High compliance
            elif compliance_mean > 0.6:
                colors.append("#f39c12")  # Orange - Moderate
            else:
                colors.append("#e74c3c")  # Red - Low compliance

    # Sort by compliance rate
    sorted_indices = np.argsort(compliance_means)[::-1]
    models = [models[i] for i in sorted_indices]
    compliance_means = [compliance_means[i] for i in sorted_indices]
    compliance_stds = [compliance_stds[i] for i in sorted_indices]
    colors = [colors[i] for i in sorted_indices]

    fig, ax = plt.subplots(figsize=(14, 8))

    y_pos = np.arange(len(models))
    ax.barh(y_pos, compliance_means, color=colors, alpha=0.8)

    # Add percentage labels (positioned to avoid bars)
    for i, mean in enumerate(compliance_means):
        ax.text(mean + 0.02, i, f"{mean * 100:.1f}%", va="center", fontsize=10, fontweight="bold")

    # Add reference lines
    ax.axvline(x=0.9, color="green", linestyle="--", alpha=0.5, linewidth=2, label="High (>90%)")
    ax.axvline(
        x=0.6, color="orange", linestyle="--", alpha=0.5, linewidth=2, label="Moderate (>60%)"
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(models, fontsize=10)
    ax.set_xlabel(
        "Compliance Rate (Willingness to Generate Content)", fontsize=12, fontweight="bold"
    )
    ax.set_title(
        "Model Compliance Rates - Higher Means More Willing to Comply",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )
    ax.set_xlim(0, max(compliance_means) * 1.15)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig(output_dir / "6_compliance_rates.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 6_compliance_rates.png")
    plt.close()


def plot_performance_vs_quality(data, output_dir):
    """
    Plot 7: Performance Trade-offs
    Shows generation time vs quality to identify efficient models
    """
    models = []
    gen_times = []
    overall_scores = []

    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"] and model_data["performance_metrics"].get(
            "generation_time_seconds"
        ):
            models.append(clean_model_name(model_id))
            gen_times.append(model_data["performance_metrics"]["generation_time_seconds"]["mean"])
            overall_scores.append(model_data["quality_metrics"]["overall_score"]["mean"])

    if not models:
        print("⚠️  No models have generation time data. Skipping plot 7.")
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    # Create scatter plot
    ax.scatter(gen_times, overall_scores, s=200, alpha=0.6, c=overall_scores, cmap="viridis")

    # Add model labels
    for i, model in enumerate(models):
        ax.annotate(
            model,
            (gen_times[i], overall_scores[i]),
            fontsize=9,
            ha="left",
            va="bottom",
            xytext=(5, 5),
            textcoords="offset points",
        )

    # Highlight ideal quadrant (low time, high quality) - top LEFT quadrant
    mean_time = np.mean(gen_times)
    mean_quality = np.mean(overall_scores)
    ax.fill_between(
        [0, mean_time],
        mean_quality,
        1.0,
        alpha=0.1,
        color="green",
        label="Ideal: Fast + High Quality",
    )

    # Add quadrant lines
    ax.axhline(y=mean_quality, color="gray", linestyle="--", alpha=0.3, linewidth=1)
    ax.axvline(x=mean_time, color="gray", linestyle="--", alpha=0.3, linewidth=1)

    ax.set_xlabel(
        "Average Generation Time (seconds) - Lower is Better", fontsize=12, fontweight="bold"
    )
    ax.set_ylabel("Overall Quality Score - Higher is Better", fontsize=12, fontweight="bold")
    ax.set_title(
        "Performance vs Quality: Ideal Models Are Top-Left (Fast + High Quality)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "7_performance_vs_quality.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 7_performance_vs_quality.png")
    plt.close()


def plot_quality_vs_compliance_scatter(data, output_dir):
    """
    Plot 8: Quality vs Compliance - Alternative view
    Simple scatter without quadrants for cleaner presentation
    """
    models = []
    overall_scores = []
    compliance_rates = []

    for model_id, model_data in data["models"].items():
        if model_data["quality_metrics"]["overall_score"]:
            models.append(clean_model_name(model_id))
            overall_scores.append(model_data["quality_metrics"]["overall_score"]["mean"])
            compliance_rates.append(model_data["quality_metrics"]["refusal"]["mean"])

    fig, ax = plt.subplots(figsize=(14, 10))

    # Create scatter plot with simple uniform color
    ax.scatter(
        compliance_rates,
        overall_scores,
        s=300,
        alpha=0.6,
        color="#3498db",
        edgecolors="black",
        linewidths=1.5,
    )

    # Add model labels
    for i, model in enumerate(models):
        ax.annotate(
            model,
            (compliance_rates[i], overall_scores[i]),
            fontsize=10,
            ha="center",
            va="top",
            xytext=(0, -10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.8, edgecolor="gray"),
        )

    # Find best model (highest combined score)
    combined_scores = [(c + o) / 2 for c, o in zip(compliance_rates, overall_scores)]
    best_idx = np.argmax(combined_scores)
    ax.scatter(
        [compliance_rates[best_idx]],
        [overall_scores[best_idx]],
        s=600,
        facecolors="none",
        edgecolors="gold",
        linewidths=5,
        zorder=10,
        label="Best Overall",
    )

    ax.set_xlabel("Compliance Rate (Higher = More Willing) →", fontsize=13, fontweight="bold")
    ax.set_ylabel("Overall Quality Score →", fontsize=13, fontweight="bold")
    ax.set_title("Quality vs Compliance - Model Comparison", fontsize=16, fontweight="bold", pad=20)

    ax.legend(loc="lower left", fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "8_quality_vs_compliance.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 8_quality_vs_compliance.png")
    plt.close()


def plot_input_length_vs_generation_time(data, output_dir):
    """
    Plot 9: Input Length vs Generation Time Analysis
    Shows how generation time scales with input length for each model
    """
    models_with_data = []

    for model_id, model_data in data["models"].items():
        perf_metrics = model_data.get("performance_metrics", {})
        input_analysis = perf_metrics.get("input_length_analysis")

        if input_analysis and "sample_data_points" in input_analysis:
            models_with_data.append(
                {"name": clean_model_name(model_id), "analysis": input_analysis}
            )

    if not models_with_data:
        print("⚠️  No models have input length analysis data. Skipping plot 9.")
        return

    # Create subplots - dynamically size based on number of models
    num_models = len(models_with_data)
    # Calculate optimal grid size
    ncols = min(3, num_models)  # Max 3 columns
    nrows = (num_models + ncols - 1) // ncols  # Ceiling division

    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 5 * nrows))
    # Handle case where there's only one subplot
    if num_models == 1:
        axes = np.array([axes])
    axes = axes.flatten() if num_models > 1 else axes

    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]

    for idx, model_info in enumerate(models_with_data):
        ax = axes[idx]
        analysis = model_info["analysis"]
        model_name = model_info["name"]

        # Extract data points
        points = analysis["sample_data_points"]["points"]
        input_tokens = [p["input_tokens"] for p in points]
        gen_times = [p["generation_time_seconds"] for p in points]

        # Scatter plot
        ax.scatter(
            input_tokens,
            gen_times,
            alpha=0.6,
            s=50,
            color=colors[idx % len(colors)],
            label="Actual data",
        )

        # Add regression line if available
        if "linear_regression" in analysis:
            reg = analysis["linear_regression"]
            slope = reg["slope"]
            intercept = reg["intercept"]

            # Generate regression line
            x_range = np.linspace(min(input_tokens), max(input_tokens), 100)
            y_pred = slope * x_range + intercept
            ax.plot(
                x_range,
                y_pred,
                "r--",
                linewidth=2,
                label=f"Linear fit: y = {slope:.2f}x + {intercept:.2f}",
            )

            # Add interpretation text
            interp = reg.get("interpretation", "")
            ax.text(
                0.05,
                0.95,
                interp,
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

        # Add correlation info
        if "correlation_coefficient" in analysis:
            corr = analysis["correlation_coefficient"]
            corr_text = f"Correlation: {corr:.3f}"
            if abs(corr) < 0.3:
                corr_text += " (weak)"
            elif abs(corr) < 0.7:
                corr_text += " (moderate)"
            else:
                corr_text += " (strong)"

            ax.text(
                0.05,
                0.85,
                corr_text,
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
            )

        ax.set_xlabel("Input Tokens", fontsize=11, fontweight="bold")
        ax.set_ylabel("Generation Time (seconds)", fontsize=11, fontweight="bold")
        ax.set_title(f"{model_name}", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.3)

    # Hide unused subplots if any
    total_subplots = nrows * ncols
    for idx in range(num_models, total_subplots):
        axes[idx].axis("off")

    fig.suptitle(
        "Input Length vs Generation Time - Model Scaling Analysis",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()
    plt.savefig(output_dir / "9_input_length_analysis.png", dpi=DPI, bbox_inches="tight")
    print("✅ Saved: 9_input_length_analysis.png")
    plt.close()

    # Also create a combined comparison plot
    if len(models_with_data) > 1:
        fig, ax = plt.subplots(figsize=(14, 8))

        for idx, model_info in enumerate(models_with_data):
            analysis = model_info["analysis"]
            model_name = model_info["name"]

            # Extract bucketed data if available
            if "input_length_buckets" in analysis:
                buckets = analysis["input_length_buckets"]
                bucket_names = []
                avg_times = []

                # Dynamically get all bucket names from the data
                all_bucket_names = sorted(buckets.keys(), key=lambda x: (
                    int(x.split('-')[0]) if '-' in x and x.split('-')[0].isdigit()
                    else int(x.rstrip('+')) if x.endswith('+') else 0
                ))

                for bucket_name in all_bucket_names:
                    if bucket_name in buckets:
                        bucket_names.append(bucket_name)
                        avg_times.append(buckets[bucket_name]["avg_time_seconds"])

                if bucket_names:
                    bar_width = 0.8 / len(models_with_data)
                    x_positions = np.arange(len(bucket_names)) + idx * bar_width
                    ax.bar(
                        x_positions,
                        avg_times,
                        width=bar_width,
                        label=model_name,
                        color=colors[idx % len(colors)],
                        alpha=0.8,
                    )

        # Only set these if we actually plotted data
        if bucket_names:
            ax.set_xlabel("Input Token Range", fontsize=12, fontweight="bold")
            ax.set_ylabel("Average Generation Time (seconds)", fontsize=12, fontweight="bold")
            ax.set_title(
                "Generation Time by Input Length Range - Model Comparison",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            center_offset = (len(models_with_data) - 1) * bar_width / 2
            ax.set_xticks(np.arange(len(bucket_names)) + center_offset)
            ax.set_xticklabels(bucket_names)
            ax.legend(loc="upper left", fontsize=10)
            ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        plt.savefig(output_dir / "9b_input_length_comparison.png", dpi=DPI, bbox_inches="tight")
        print("✅ Saved: 9b_input_length_comparison.png")
        plt.close()


def main():
    """Generate all plots."""
    print("📊 Generating Model Comparison Plots for Sprint Review")
    print("=" * 60)

    # Load report
    report_path = Path(REPORT_PATH)
    if not report_path.exists():
        print(f"❌ Report not found: {report_path}")
        return 1

    print(f"📂 Loading report from: {report_path}")
    data = load_report(report_path)

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    print(f"📈 Generating plots for {data['metadata']['total_models']} models...")
    print("=" * 60 + "\n")

    # Generate all plots
    plot_overall_ranking(data, output_dir)
    plot_safety_quality_tradeoff(data, output_dir)
    plot_radar_chart(data, output_dir)
    plot_model_summary_table(data, output_dir)
    plot_metric_breakdown(data, output_dir)
    plot_compliance_focus(data, output_dir)
    plot_performance_vs_quality(data, output_dir)
    plot_quality_vs_compliance_scatter(data, output_dir)
    plot_input_length_vs_generation_time(data, output_dir)

    print("\n" + "=" * 60)
    print("✅ All plots generated successfully!")
    print(f"📂 Plots saved to: {output_dir}")
    print("\n📋 Plot Summary:")
    print("  1. Overall Ranking - Winner and tier breakdown")
    print("  2. Selection Matrix - Quality vs Compliance trade-offs")
    print("  3. Top 3 Comparison - Detailed radar chart")
    print("  4. Summary Table - Complete comparison table")
    print("  5. Metric Breakdown - Detailed bar chart")
    print("  6. Compliance Focus - Compliance rates with error bars")
    print("  7. Performance vs Quality - Generation time trade-offs")
    print("  8. Quality vs Compliance - Alternative scatter view")
    print("  9. Input Length Analysis - Scaling analysis with regression")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
