"""Statistics module for comprehensive data analysis and reporting.

This module provides a clean interface for statistics calculations throughout the application.
It includes support for entity statistics, test result analytics, and historical trends.

Main Components:
- StatsCalculator: Core class for general entity statistics
- get_test_stats: Specialized function for test entity statistics
- get_individual_test_stats: Specialized function for individual test analysis
- get_test_result_stats: Specialized function for test result analytics
- get_test_run_stats: Specialized function for test run analytics
"""

# Core classes and configurations
from .calculator import StatsCalculator
from .config import DimensionInfo, StatsConfig, StatsResult

# Specialized functions
from .test import get_individual_test_stats, get_test_stats
from .test_result import get_test_result_stats
from .test_run import get_test_run_stats
from .utils import timer

__all__ = [
    # Core classes
    "StatsConfig",
    "DimensionInfo",
    "StatsResult",
    "StatsCalculator",
    # Utilities
    "timer",
    # Main functions
    "get_test_stats",
    "get_individual_test_stats",
    "get_test_result_stats",
    "get_test_run_stats",
]
