"""ShowChartTool: validates the chart request, runs the query, keeps the numbers out of
the model's hands."""

import json

import pytest

from rhesis.sdk.agents.chart_tool import MAX_ROWS, ShowChartTool
from rhesis.sdk.agents.schemas import ToolResult

SCHEMA = {
    "entities": {
        "test_result": {
            "measures": {
                "count": {"kind": "count"},
                "pass_rate": {"kind": "rate"},
                "p95_duration_ms": {"kind": "duration"},
            },
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
    # The query is capped one row past what a chart shows, so a huge breakdown stays cheap.
    assert insights_args["limit"] == MAX_ROWS + 1
    assert tool.drain() == []


@pytest.mark.asyncio
async def test_summary_gives_the_real_labels_and_values():
    """Without them the model narrated invented category names beside the real chart."""
    tool, _ = _tool(TOPIC_ROWS)

    result = await tool.execute(**BAR)

    assert "- Claims: pass_rate=25.0" in result.content
    assert "- Billing: pass_rate=60.0" in result.content
    assert "don't repeat them as a table" in result.content


@pytest.mark.asyncio
async def test_summary_elides_long_charts_but_keeps_both_ends():
    rows = [{"topic": f"t{i}", "pass_rate": float(i)} for i in range(40)]
    tool, _ = _tool(rows)

    result = await tool.execute(**BAR)

    assert "- t0:" in result.content and "- t39:" in result.content
    assert "- t20:" not in result.content and "more rows" in result.content


@pytest.mark.asyncio
async def test_elided_summary_still_names_the_true_extremes():
    """The peak hid in the elided middle, and the model reported a smaller one as the peak."""
    rows = [{"topic": f"t{i}", "pass_rate": 50.0} for i in range(40)]
    rows[20] = {"topic": "peak", "pass_rate": 99.0}
    rows[25] = {"topic": "trough", "pass_rate": 1.0}
    tool, _ = _tool(rows)

    result = await tool.execute(**BAR)

    assert "highest pass_rate: peak: pass_rate=99.0" in result.content
    assert "lowest pass_rate: trough: pass_rate=1.0" in result.content


def _trend(group_by, order_by=None):
    query = {"entity": "test_result", "group_by": group_by, "measures": ["pass_rate"]}
    if order_by:
        query["order_by"] = order_by
    return {
        "query": query,
        "chart_type": "line",
        "title": "Trend",
        "x": "period",
        "series": "topic" if "topic" in group_by else None,
        "y": ["pass_rate"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group_by, order_by, expected",
    [
        (["period"], None, "in time order"),
        (["period"], ["-pass_rate"], "in the order shown"),
        (["topic", "period"], None, "in the order shown"),
    ],
)
async def test_summary_claims_time_order_only_when_rows_are_sorted_by_period(
    group_by, order_by, expected
):
    """Sorting by a measure, or by another dimension first, breaks chronological order."""
    rows = [{"period": "2026-10-01", "topic": "Claims", "pass_rate": 80.0}]
    tool, _ = _tool(rows)

    result = await tool.execute(**_trend(group_by, order_by))

    assert expected in result.content


@pytest.mark.asyncio
async def test_extremes_of_a_truncated_chart_name_the_rows_they_cover():
    rows = [{"topic": f"t{i}", "pass_rate": float(i)} for i in range(MAX_ROWS + 5)]
    tool, _ = _tool(rows)

    result = await tool.execute(**BAR)

    assert f"Across the first {MAX_ROWS} rows, lowest pass_rate" in result.content
    assert "Across all rows" not in result.content


@pytest.mark.asyncio
async def test_summary_labels_a_missing_dimension_value_as_none():
    tool, _ = _tool([{"topic": None, "pass_rate": 40.0}])

    result = await tool.execute(**BAR)

    assert "- (none): pass_rate=40.0" in result.content


@pytest.mark.asyncio
async def test_measures_of_different_kinds_are_rejected():
    tool, _ = _tool([{"period": "2026-10-01", "pass_rate": 80.0, "p95_duration_ms": 2100.0}])

    result = await tool.execute(
        query={
            "entity": "test_result",
            "group_by": ["period"],
            "measures": ["pass_rate", "p95_duration_ms"],
        },
        chart_type="line",
        title="Mixed",
        x="period",
        y=["pass_rate", "p95_duration_ms"],
    )

    assert not result.success and "one chart per kind" in result.error
    assert tool.drain() == []


@pytest.mark.asyncio
async def test_rows_are_capped():
    rows = [{"topic": f"t{i}", "pass_rate": float(i)} for i in range(MAX_ROWS + 5)]
    tool, _ = _tool(rows)

    await tool.execute(**BAR)

    (chart,) = tool.drain()
    assert len(chart["rows"]) == MAX_ROWS and chart["truncated"] is True


@pytest.mark.asyncio
async def test_a_smaller_limit_is_kept():
    tool, calls = _tool(TOPIC_ROWS)

    await tool.execute(**{**BAR, "query": {**BAR["query"], "limit": 5}})

    assert dict(calls)["get_insights"]["limit"] == 5


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
