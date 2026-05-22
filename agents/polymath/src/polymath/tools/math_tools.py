"""Local Python math tools for the Math Specialist agent.

These are intentionally trivial. Their value is not arithmetic correctness but
the ``ai.tool.invoke`` spans MAF emits every time the agent calls them, which
the SDK's :mod:`rhesis.sdk.telemetry.integrations.agent_framework` translator
rewrites into the Rhesis schema.
"""

from __future__ import annotations

import math
from typing import Annotated

from agent_framework import tool
from pydantic import Field


@tool
def add(
    a: Annotated[float, Field(description="First operand.")],
    b: Annotated[float, Field(description="Second operand.")],
) -> float:
    """Return the sum of two numbers."""
    return a + b


@tool
def multiply(
    a: Annotated[float, Field(description="First operand.")],
    b: Annotated[float, Field(description="Second operand.")],
) -> float:
    """Return the product of two numbers."""
    return a * b


@tool
def power(
    base: Annotated[float, Field(description="The base.")],
    exponent: Annotated[float, Field(description="The exponent.")],
) -> float:
    """Return ``base`` raised to ``exponent``."""
    return math.pow(base, exponent)


@tool
def square_root(
    x: Annotated[float, Field(description="A non-negative number.")],
) -> float:
    """Return the non-negative square root of ``x``.

    Raises:
        ValueError: if ``x`` is negative.
    """
    if x < 0:
        raise ValueError(f"square_root requires x >= 0, got {x}")
    return math.sqrt(x)


MATH_TOOLS = [add, multiply, power, square_root]
