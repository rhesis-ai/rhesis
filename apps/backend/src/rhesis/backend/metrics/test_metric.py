#!/usr/bin/env python3
"""
Simple command-line script to test metrics by ID.

Usage:
    # With manual parameters
    python test_metric.py <metric_id> --org <org_id> --user <user_id> --input "Your question" --output "Model response" --expected "Expected response"
    
    # With test data from database
    python test_metric.py <metric_id> --org <org_id> --user <user_id> --test-id <test_id> --output "Model response"
    
    # Show only the rendered template (no evaluation)
    python test_metric.py <metric_id> --org <org_id> --user <user_id> --input "Your question" --template-only

Examples:
    # Manual parameters
    python test_metric.py abc123 \
        --org org123 --user user456 \
        --input "What is the capital of France?" \
        --output "Paris is the capital of France." \
        --expected "The capital of France is Paris." \
        --context "France is a country in Europe."
    
    # Using existing test data
    python test_metric.py abc123 \
        --org org123 --user user456 \
        --test-id test123 \
        --output "Paris is the capital of France."
    
    # Show only the rendered template
    python test_metric.py abc123 \
        --org org123 --user user456 \
        --input "What is the capital of France?" \
        --template-only
"""

import argparse
import json
import os
import sys
from typing import List, Optional
from uuid import UUID

# Add the backend to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric
from rhesis.backend.app.models.test import Test


class MockUser:
    """Mock user object for providing context, similar to runner.py."""

    def __init__(self, user_id: str, organization_id: str):
        self.id = user_id
        self.organization_id = organization_id


def load_metric_from_db(db: Session, metric_id: str, organization_id: str) -> Optional[Metric]:
    """
    Load a metric from the database by ID with organization filtering.

    SECURITY: This function requires organization_id to prevent data leakage across organizations.
    """
    try:
        # Try as UUID first
        metric_uuid = UUID(metric_id)
        metric = (
            db.query(Metric)
            .filter(Metric.id == metric_uuid, Metric.organization_id == organization_id)
            .first()
        )
        if metric:
            return metric
    except ValueError:
        pass

    # Try as nano_id
    metric = (
        db.query(Metric)
        .filter(Metric.nano_id == metric_id, Metric.organization_id == organization_id)
        .first()
    )
    if metric:
        return metric

    # Try as name
    metric = (
        db.query(Metric)
        .filter(Metric.name == metric_id, Metric.organization_id == organization_id)
        .first()
    )
    return metric


def load_test_from_db(db: Session, test_id: str, organization_id: str) -> Optional[Test]:
    """
    Load a test from the database by ID with organization filtering.

    SECURITY: This function requires organization_id to prevent data leakage across organizations.
    """
    try:
        # Try as UUID first
        test_uuid = UUID(test_id)
        test = (
            db.query(Test)
            .filter(Test.id == test_uuid, Test.organization_id == organization_id)
            .first()
        )
        if test:
            return test
    except ValueError:
        pass

    # Try as nano_id
    test = (
        db.query(Test)
        .filter(Test.nano_id == test_id, Test.organization_id == organization_id)
        .first()
    )
    return test


def extract_test_data(test: Test) -> tuple:
    """Extract input text, expected output, and context from a test object."""
    input_text = ""
    expected_output = ""
    context = []

    if test.prompt:
        input_text = test.prompt.content or ""
        # Expected response is in the prompt model
        expected_output = test.prompt.expected_response or ""

    # Extract context from test_contexts if available
    if hasattr(test, "test_contexts") and test.test_contexts:
        for test_context in test.test_contexts:
            if hasattr(test_context, "attributes") and test_context.attributes:
                # Extract context from attributes if it's stored there
                context_data = test_context.attributes.get("context", "")
                if context_data:
                    context.append(context_data)

    return input_text, expected_output, context


def run_metric_test(
    metric_id: str,
    organization_id: str,
    user_id: str,
    input_text: Optional[str] = None,
    output_text: Optional[str] = None,
    expected_output: Optional[str] = None,
    context: Optional[List[str]] = None,
    test_id: Optional[str] = None,
    template_only: bool = False,
) -> dict:
    """Test a metric with the given parameters."""

    # Create mock user for context
    mock_user = MockUser(user_id=user_id, organization_id=organization_id)

    # Use simple database session and pass tenant context directly
    from rhesis.backend.app.database import get_db

    try:
        with get_db() as db_session:
            print(
                f"🔑 Using database session with direct tenant context: org={organization_id}, user={user_id}"
            )

            return _execute_metric_test(
                db_session=db_session,
                mock_user=mock_user,
                metric_id=metric_id,
                organization_id=organization_id,
                user_id=user_id,
                input_text=input_text,
                output_text=output_text,
                expected_output=expected_output,
                context=context,
                test_id=test_id,
                template_only=template_only,
            )

    except Exception as e:
        print(f"⚠️  Error during metric test: {e}")
        return {"error": str(e)}


def _execute_metric_test(
    db_session,
    mock_user,
    metric_id: str,
    organization_id: str,
    user_id: str,
    input_text: Optional[str] = None,
    output_text: Optional[str] = None,
    expected_output: Optional[str] = None,
    context: Optional[List[str]] = None,
    test_id: Optional[str] = None,
    template_only: bool = False,
) -> dict:
    """Execute the metric test with the provided database session."""
    try:
        # Load test data if test_id is provided
        if test_id:
            print(f"🧪 Loading test data: {test_id}")
            test_model = load_test_from_db(db_session, test_id, organization_id)

            if not test_model:
                print(f"❌ Test not found: {test_id}")
                print("💡 Available tests:")
                tests = db_session.query(Test).limit(5).all()
                for t in tests:
                    print(
                        f"   - {t.nano_id}: {t.prompt.content[:50] if t.prompt else 'No prompt'}..."
                    )
                return {"error": f"Test not found: {test_id}"}

            # Extract test data
            test_input, test_expected, test_context = extract_test_data(test_model)

            # Use test data if not overridden by command line
            if input_text is None:
                input_text = test_input
            if expected_output is None:
                expected_output = test_expected
            if not context:
                context = test_context

            print("✅ Test data loaded:")
            print(f"   Input: {input_text[:100]}{'...' if len(input_text) > 100 else ''}")
            print(
                f"   Expected: {expected_output[:100]}{'...' if len(expected_output) > 100 else ''}"
            )

        # Load metric from database
        print(f"📊 Loading metric: {metric_id}")
        metric_model = load_metric_from_db(db_session, metric_id, organization_id)

        if not metric_model:
            print(f"❌ Metric not found: {metric_id}")
            print("💡 Available metrics:")
            metrics = db_session.query(Metric).limit(5).all()
            for m in metrics:
                print(f"   - {m.nano_id or m.id}: {m.name}")
            return {"error": f"Metric not found: {metric_id}"}

        print(f"✅ Metric loaded: {metric_model.name} ({metric_model.class_name})")

        # Dynamic imports to avoid circular dependencies
        from rhesis.backend.metrics.evaluator import MetricEvaluator

        # Pass the Metric model directly - evaluator handles conversion
        print("✅ Using Metric model directly (evaluator handles conversion)...")
        metric_config = metric_model

        # Initialize evaluator and run evaluation
        print("\n🚀 Running evaluation...")
        evaluator = MetricEvaluator()

        # Set defaults
        context = context or []
        expected_output = expected_output or ""

        # If template_only mode, we don't need output_text
        if not template_only:
            # Ensure we have the required parameters for evaluation
            if not output_text:
                return {"error": "output_text is required"}

        if not input_text:
            return {"error": "input_text is required (either via --input or --test-id)"}

        print("📝 Evaluation parameters:")
        print(f"   Input: {input_text[:100]}{'...' if len(input_text) > 100 else ''}")
        print(
            f"   Output: {output_text[:100] if output_text else '(template-only mode)'}{'...' if output_text and len(output_text) > 100 else ''}"
        )
        print(f"   Expected: {expected_output[:100]}{'...' if len(expected_output) > 100 else ''}")
        print(f"   Context items: {len(context)}")

        # If template_only mode, just get and return the template
        if template_only:
            print("\n📝 TEMPLATE ONLY MODE - Getting rendered template...")
            try:
                if metric_config.backend == "rhesis":
                    from rhesis.backend.metrics.rhesis.factory import RhesisMetricFactory

                    factory = RhesisMetricFactory()
                    metric_params = {
                        "threshold": metric_config.threshold,
                        **metric_config.parameters,
                    }
                    metric = factory.create(metric_config.class_name, **metric_params)

                    if hasattr(metric, "get_prompt_template"):
                        rendered_template = metric.get_prompt_template(
                            input=input_text,
                            output=output_text or "[PLACEHOLDER OUTPUT]",
                            expected_output=expected_output or "",
                            context=context or [],
                        )
                        return {"_rendered_template": rendered_template}
                    else:
                        return {"error": "Metric does not support template rendering"}
                else:
                    return {"error": "Template rendering only supported for Rhesis metrics"}
            except Exception as e:
                return {"error": f"Failed to render template: {str(e)}"}

        # Run evaluation
        results = evaluator.evaluate(
            input_text=input_text,
            output_text=output_text,
            expected_output=expected_output,
            context=context,
            metrics=[metric_config],
            max_workers=1,
        )

        # Try to get the rendered template and run direct evaluation for raw details
        rendered_template = None
        raw_metric_result = None

        if metric_config.backend == "rhesis":
            try:
                # Create the metric instance to get the rendered template and raw results
                from rhesis.backend.metrics.rhesis.factory import RhesisMetricFactory

                factory = RhesisMetricFactory()
                metric_params = {"threshold": metric_config.threshold, **metric_config.parameters}
                metric = factory.create(metric_config.class_name, **metric_params)

                # Get the rendered template if the metric has this capability
                if hasattr(metric, "get_prompt_template"):
                    rendered_template = metric.get_prompt_template(
                        input=input_text,
                        output=output_text,
                        expected_output=expected_output or "",
                        context=context or [],
                    )

                # Run the metric directly to get raw details
                try:
                    raw_metric_result = metric.evaluate(
                        input=input_text,
                        output=output_text,
                        expected_output=expected_output,
                        context=context or [],
                    )
                except Exception as e:
                    print(f"⚠️  Could not get raw metric result: {e}")

            except Exception as e:
                print(f"⚠️  Could not retrieve rendered template: {e}")

        # Add rendered template and raw details to results if available
        if rendered_template:
            results["_rendered_template"] = rendered_template

        if raw_metric_result:
            # Add the raw metric details to the results
            for metric_name, result in results.items():
                if metric_name != "_rendered_template" and isinstance(result, dict):
                    result["raw_details"] = raw_metric_result.details

        return results

    except Exception as e:
        return {"error": f"Failed to test metric: {str(e)}"}
    finally:
        db_session.close()


def print_results(results: dict, debug: bool = False):
    """Print results in a readable format."""
    if "error" in results:
        print(f"\n❌ Error: {results['error']}")
        return

    # Check if we have a rendered template to show
    rendered_template = results.get("_rendered_template")
    if rendered_template:
        print("\n📝 RENDERED EVALUATION TEMPLATE")
        print("=" * 60)
        print(rendered_template)
        print("=" * 60)

    print("\n📊 EVALUATION RESULTS")
    print("=" * 50)

    for metric_name, result in results.items():
        # Skip the rendered template in results display
        if metric_name == "_rendered_template":
            continue

        if isinstance(result, dict) and "error" in result:
            print(f"\n❌ {metric_name}: {result['error']}")
            continue

        print(f"\n🎯 {metric_name}")
        print("-" * 30)

        if isinstance(result, dict):
            print(f"Score: {result.get('score', 'N/A')}")
            print(f"Success: {'✅' if result.get('is_successful', False) else '❌'}")
            print(f"Backend: {result.get('backend', 'Unknown')}")

            reason = result.get("reason", "")
            if reason:
                print(f"Reason: {reason}")

            # Show raw LLM response and score processing details if debug mode
            if debug:
                details = result.get("raw_details", {}) or result.get("details", {})
                if details:
                    print("\n🔍 DETAILED ANALYSIS:")

                    # Raw LLM response
                    raw_response = details.get("llm_response", "")
                    if raw_response:
                        print(f"Raw LLM Response: {raw_response}")

                        # Score processing details
                raw_score = details.get("raw_score")
                processed_score = details.get("processed_score")
                final_score = details.get("final_score") or details.get(
                    "normalized_score"
                )  # Support both old and new field names

                if raw_score is not None:
                    print(f"Raw Score: {raw_score}")
                if processed_score is not None:
                    print(f"Processed Score: {processed_score}")
                if final_score is not None:
                    print(f"Final Score: {final_score}")

                    # Score type and thresholds
                score_type = details.get("score_type")
                if score_type:
                    print(f"Score Type: {score_type}")

                threshold = details.get("threshold")
                if threshold is not None:
                    print(f"Threshold: {threshold}")

                # Show normalized threshold if different from raw threshold
                normalized_threshold = details.get("normalized_threshold")
                if normalized_threshold is not None and normalized_threshold != threshold:
                    print(f"Normalized Threshold: {normalized_threshold}")

                reference_score = details.get("reference_score")
                if reference_score is not None:
                    print(f"Reference Score: {reference_score}")

                # Min/Max scores for normalization
                min_score = details.get("min_score")
                max_score = details.get("max_score")
                if min_score is not None and max_score is not None:
                    print(f"Score Range: {min_score} - {max_score}")

        else:
            print(f"Result: {result}")


def main():
    parser = argparse.ArgumentParser(description="Test a metric with given parameters")
    parser.add_argument("metric_id", help="Metric ID (UUID, nano_id, or name)")
    parser.add_argument(
        "--org", dest="organization_id", required=True, help="Organization ID for database context"
    )
    parser.add_argument(
        "--user", dest="user_id", required=True, help="User ID for database context"
    )
    parser.add_argument(
        "--test-id", "-t", help="Test ID to load input/expected data from (UUID or nano_id)"
    )
    parser.add_argument("--input", "-i", help="Input query/question (overrides test data)")
    parser.add_argument("--output", "-o", help="Model output to evaluate")
    parser.add_argument("--expected", "-e", help="Expected/reference output (overrides test data)")
    parser.add_argument(
        "--context",
        "-c",
        action="append",
        default=[],
        help="Context chunks (can be used multiple times)",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--debug", action="store_true", help="Show detailed score processing and raw LLM responses"
    )
    parser.add_argument(
        "--template-only",
        action="store_true",
        help="Only show the rendered template without running evaluation",
    )

    args = parser.parse_args()

    # Validate required parameters
    if not args.test_id and not args.input:
        parser.error("Either --test-id or --input is required")

    if not args.output and not args.template_only:
        parser.error("--output is required (unless using --template-only)")

    if args.verbose:
        print("🔍 Test Parameters:")
        print(f"   Metric ID: {args.metric_id}")
        print(f"   Organization ID: {args.organization_id}")
        print(f"   User ID: {args.user_id}")
        if args.test_id:
            print(f"   Test ID: {args.test_id}")
        print(f"   Input: {args.input or '(from test)'}")
        print(f"   Output: {args.output}")
        print(f"   Expected: {args.expected or '(from test)'}")
        print(f"   Context: {args.context}")
        print()

    # Run the test
    results = run_metric_test(
        metric_id=args.metric_id,
        organization_id=args.organization_id,
        user_id=args.user_id,
        input_text=args.input,
        output_text=args.output,
        expected_output=args.expected,
        context=args.context,
        test_id=args.test_id,
        template_only=args.template_only,
    )

    # Output results
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_results(results, debug=args.debug)


if __name__ == "__main__":
    main()
