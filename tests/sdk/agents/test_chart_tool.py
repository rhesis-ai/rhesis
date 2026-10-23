"""ShowChartTool: validates the chart request, runs the query, keeps the numbers out of
the model's hands."""

import json

import pytest

from rhesis.sdk.agents.chart_tool import MAX_ROWS, ShowChartTool
from rhesis.sdk.agents.schemas import ToolResult

SCHEMA = {
    "entities": {
        "test_result": {
            "measures": {"count": {"kind": "count"}, "pass_rate": {"kind": "rate"}},
        }
    }
}


def _tool(rows, success=True):
    calls = []

    async def run_tool(name, args):
        calls.append((name, args))
        if name == "describe_insights":
            return ToolResult(tool_name=name, success=True, content=json.dumps(SCHEMA))
        if not success:
            return ToolResult(tool_name=name, success=False, error="boom")
        envelope = {"entity": args["entity"], "rows": rows, "time_grain": args.get("time_grain")}
        return ToolResult(tool_name=name, success=True, content=json.dumps(envelope))

    return ShowChartTool(run_tool), calls


TOPIC_ROWS = [
    {"topic": "Claims", "topic_id": "t1", "count": 4, "pass_rate": 25.0},
    {"topic": "Billing", "topic_id": "t2", "count": 6, "pass_rate": 60.0},
]
BAR = {
    "query": {
        "entity": "test_result",
        "group_by": ["topic"],
        "measures": ["count", "pass_rate"],
        "order_by": ["pass_rate"],
        "filters": {"test_run_ids": ["r1"]},
    },
    "chart_type": "horizontal_bar",
    "title": "Weakest topics",
    "x": "topic",
    "y": ["pass_rate"],
}


@pytest.mark.asyncio
async def test_chart_carries_the_query_rows_and_measure_kinds():
    tool, calls = _tool(TOPIC_ROWS)

    result = await tool.execute(**BAR)

    assert result.success
    (chart,) = tool.drain()
    assert chart["rows"] == TOPIC_ROWS
    assert chart["measures"] == [{"key": "pass_rate", "kind": "rate"}]
    assert chart["chart_type"] == "horizontal_bar" and chart["x"] == "topic"
    # Nested filters are flattened into get_insights' own arguments.
    insights_args = dict(calls)["get_insights"]
    assert insights_args["test_run_ids"] == ["r1"] and "filters" not in insights_args
    assert tool.drain() == []


@pytest.mark.asyncio
async def test_summary_gives_ranges_not_rows():
    tool, _ = _tool(TOPIC_ROWS)

    result = await tool.execute(**BAR)

    assert "pass_rate 25.0-60.0" in result.content
    assert "Claims" not in result.content


@pytest.mark.asyncio
async def test_rows_are_capped():
    rows = [{"topic": f"t{i}", "pass_rate": float(i)} for i in range(MAX_ROWS + 5)]
    tool, _ = _tool(rows)

    await tool.execute(**BAR)

    (chart,) = tool.drain()
    assert len(chart["rows"]) == MAX_ROWS and chart["truncated"] is True


@pytest.mark.asyncio
async def test_no_rows_shows_no_chart():
    tool, _ = _tool([])

    result = await tool.execute(**BAR)

    assert result.success and "no data" in result.content
    assert tool.drain() == []


@pytest.mark.asyncio
async def test_query_failure_is_reported():
    tool, _ = _tool(TOPIC_ROWS, success=False)

    result = await tool.execute(**BAR)

    assert not result.success and "boom" in result.error
    assert tool.drain() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change, message",
    [
        ({"chart_type": "pie"}, "chart_type"),
        ({"y": ["passed"]}, "doesn't request"),
        ({"x": "requirement"}, "group_by"),
        ({"chart_type": "heat_table"}, "series"),
        ({"chart_type": "scatter"}, "exactly two"),
        ({"chart_type": "kpi"}, "kpi"),
        ({"y": ["count", "pass_rate"], "series": "status"}, "group_by"),
    ],
)
async def test_invalid_requests_are_rejected_before_querying(change, message):
    tool, calls = _tool(TOPIC_ROWS)

    result = await tool.execute(**{**BAR, **change})

    assert not result.success and message in result.error
    assert calls == []


@pytest.mark.asyncio
async def test_kpi_takes_no_group_by():
    tool, _ = _tool([{"pass_rate": 58.33}])

    result = await tool.execute(
        query={"entity": "test_result", "measures": ["pass_rate"]},
        chart_type="kpi",
        title="Overall pass rate",
        y=["pass_rate"],
        target=90,
    )

    assert result.success
    (chart,) = tool.drain()
    assert chart["x"] is None and chart["target"] == 90
