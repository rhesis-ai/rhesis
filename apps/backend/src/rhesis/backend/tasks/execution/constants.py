"""Constants for test execution tasks."""

from enum import Enum


class MetricScope(str, Enum):
    """
    Metric scope enum for test execution.

    These values must match:
    - Database metric_scope field (stored as JSON array)
    - SDK MetricScope enum values (sdk/src/rhesis/sdk/metrics/base.py)

    Using str as a mixin allows the enum to be used directly in string comparisons
    and serialized naturally to JSON.
    """

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"
