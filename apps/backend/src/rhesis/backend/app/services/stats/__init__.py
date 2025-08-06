"""Statistics module for comprehensive data analysis and reporting.

This module provides a clean interface for statistics calculations throughout the application.
It includes support for entity statistics, test result analytics, and historical trends.

Main Components:
- StatsCalculator: Core class for general entity statistics
- get_test_result_stats: Specialized function for test result analytics
"""

# Core classes and configurations
from .config import StatsConfig, DimensionInfo, StatsResult
from .calculator import StatsCalculator
from .utils import timer

# Specialized functions
from .test_results import get_test_result_stats

__all__ = [
    # Core classes
    "StatsConfig",
    "DimensionInfo", 
    "StatsResult",
    "StatsCalculator",
    
    # Utilities
    "timer",
    
    # Main functions
    "get_test_result_stats",
]
