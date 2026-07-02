"""Preflight check constants and labels."""

CHECK_ENDPOINT_CONNECTIVITY = "endpoint_connectivity"
CHECK_EVALUATION_MODEL = "evaluation_model"
CHECK_EXECUTION_MODEL = "execution_model"
CHECK_BEHAVIOR_METRIC_COVERAGE = "behavior_metric_coverage"
CHECK_METRIC_COMPATIBILITY = "metric_compatibility"
CHECK_METRIC_FUNCTIONALITY = "metric_functionality"
CHECK_TEST_SET_NOT_EMPTY = "test_set_not_empty"

SHARED_CHECKS = {
    CHECK_ENDPOINT_CONNECTIVITY,
    CHECK_EVALUATION_MODEL,
    CHECK_EXECUTION_MODEL,
}

PER_TEST_SET_CHECKS = {
    CHECK_TEST_SET_NOT_EMPTY,
    CHECK_BEHAVIOR_METRIC_COVERAGE,
    CHECK_METRIC_COMPATIBILITY,
    CHECK_METRIC_FUNCTIONALITY,
}

LABELS = {
    CHECK_ENDPOINT_CONNECTIVITY: "Endpoint Connectivity",
    CHECK_EVALUATION_MODEL: "Evaluation Model",
    CHECK_EXECUTION_MODEL: "Execution Model",
    CHECK_BEHAVIOR_METRIC_COVERAGE: "Behavior-Metric Coverage",
    CHECK_METRIC_COMPATIBILITY: "Metric-Endpoint Compatibility",
    CHECK_METRIC_FUNCTIONALITY: "Metric Functionality",
    CHECK_TEST_SET_NOT_EMPTY: "Test Set Has Tests",
}
