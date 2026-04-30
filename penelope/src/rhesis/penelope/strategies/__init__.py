"""
Testing strategies for Penelope.

Strategies define reusable patterns for specific types of testing
and exploration. The module provides a registry so strategies can be
looked up by name at runtime, and performance tracking so callers
can make data-driven strategy choices.

Usage::

    from rhesis.penelope.strategies import get_strategy, list_strategies

    strategy = get_strategy("domain_probing")
    goal = strategy.build_goal(target_name="My Chatbot")

    all_exploration = list_strategies(category="exploration")

Performance tracking::

    from rhesis.penelope.strategies import record_strategy_run, get_strategy_performance

    record_strategy_run("domain_probing", findings)
    stats = get_strategy_performance()  # all strategies
"""

from rhesis.penelope.strategies.base import (
    CONTEXT_FIELDS,
    STRATEGY_PERFORMANCE,
    STRATEGY_REGISTRY,
    ExplorationStrategy,
    PenelopeStrategy,
    StrategyPerformanceRecord,
    get_strategy,
    get_strategy_performance,
    list_strategies,
    record_strategy_run,
    register_strategy,
)
from rhesis.penelope.strategies.boundary_discovery import BoundaryDiscoveryStrategy
from rhesis.penelope.strategies.capability_mapping import CapabilityMappingStrategy
from rhesis.penelope.strategies.domain_probing import DomainProbingStrategy

__all__ = [
    "CONTEXT_FIELDS",
    "PenelopeStrategy",
    "ExplorationStrategy",
    "DomainProbingStrategy",
    "CapabilityMappingStrategy",
    "BoundaryDiscoveryStrategy",
    "StrategyPerformanceRecord",
    "STRATEGY_REGISTRY",
    "STRATEGY_PERFORMANCE",
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "record_strategy_run",
    "get_strategy_performance",
]
