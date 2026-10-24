"""Chart tool for agents that report on insights data.

The model picks what to chart (an insights query, a chart type, which columns go
where); the numbers come from running that query, never from the model. Each
chart is kept on the tool so the host can attach it to the reply.
"""

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from rhesis.sdk.agents.base import BaseTool
from rhesis.sdk.agents.schemas import ToolResult

logger = logging.getLogger(__name__)

RunTool = Callable[[str, Dict[str, Any]], Awaitable[ToolResult]]
"""``(tool_name, arguments) -> ToolResult`` -- runs get_insights / describe_insights."""

CHART_TYPES: Dict[str, str] = {
    "line": "trend over an ordered x such as period; one line per measure or per series value",
    "area": "stacked areas over period, for composition over time (passed/failed/error_count)",
    "bar": "compare categories; one group of bars per x value",
    "horizontal_bar": "a ranked list of categories; pair with order_by and limit",
    "stacked_bar": "composition per category: several count measures, or one split by series",
    "scatter": "how two measures relate; y names exactly two measures, one point per x value",
    "heat_table": "two dimensions at once (x by series), cells colored by one rate or score",
    "radar": "a profile across x values (for example metrics), one shape per series value",
    "kpi": "one headline number; group_by is empty and y names one measure",
}

MAX_ROWS = 200


class ShowChartTool(BaseTool):
    """Run an insights query and show its result to the user as a chart.

    Args:
        run_tool: Runs a named tool with arguments. The host passes one bound to
            the user's own credentials and project, so a chart can only show
            data the user can already read.
    """

    def __init__(self, run_tool: RunTool):
        self._run_tool = run_tool
        self._measure_kinds: Optional[Dict[str, Dict[str, str]]] = None
        self.charts: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "show_chart"

    @property
    def requires_confirmation(self) -> bool:
        return False

    @property
    def description(self) -> str:
        types = "; ".join(f"{name} = {use}" for name, use in CHART_TYPES.items())
        return (
            "Show the user a chart of a get_insights query. You choose the query and how to "
            "draw it; the numbers come from running the query, so never pass data yourself. "
            "The user sees the chart with a toggle to its exact numbers, so don't repeat the "
            "rows as a table: say what the chart shows. "
            "x and series must be the query's group_by dimensions (x alone, or x and series); "
            "y names measures from the query. "
            f"Chart types: {types}. "
            "Use min_count in the query when ranking rates."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "object",
                    "description": (
                        "get_insights arguments: entity, group_by, measures, and optionally "
                        "time_grain, order_by, limit, min_count, filters such as "
                        "test_run_ids, and months/start_date/end_date."
                    ),
                },
                "chart_type": {"type": "string", "enum": list(CHART_TYPES)},
                "title": {
                    "type": "string",
                    "description": "Short title stating what the chart shows.",
                },
                "x": {
                    "type": "string",
                    "description": "The group_by dimension on the x axis (omit for kpi).",
                },
                "y": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Measures to plot, from the query's measures.",
                },
                "series": {
                    "type": "string",
                    "description": (
                        "Optional second group_by dimension: one line, bar or shape per value. "
                        "Required for heat_table."
                    ),
                },
                "target": {
                    "type": "number",
                    "description": "Optional reference line, e.g. a 90 pass-rate target.",
                },
            },
            "required": ["query", "chart_type", "title", "y"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            spec_args = _validate(kwargs)
        except ValueError as exc:
            return self._error(str(exc))

        result = await self._run_tool("get_insights", spec_args["query"])
        if not result.success:
            return self._error(f"get_insights failed: {result.error}")
        try:
            envelope = json.loads(result.content)
        except (TypeError, ValueError):
            return self._error("get_insights returned something that isn't JSON")

        rows = envelope.get("rows") or []
        if not rows:
            return ToolResult(
                tool_name=self.name,
                success=True,
                content="The query matched no data, so no chart was shown. Tell the user so.",
            )

        kinds = await self._kinds(spec_args["query"]["entity"])
        y_kinds = {kinds.get(m, "count") for m in spec_args["y"]}
        if len(y_kinds) > 1 and spec_args["chart_type"] != "scatter":
            return self._error(
                f"y mixes measure kinds ({', '.join(sorted(y_kinds))}), which can't share an "
                "axis; show one chart per kind"
            )
        chart = {
            "title": spec_args["title"],
            "chart_type": spec_args["chart_type"],
            "entity": envelope.get("entity"),
            "x": spec_args.get("x"),
            "series": spec_args.get("series"),
            "measures": [{"key": m, "kind": kinds.get(m, "count")} for m in spec_args["y"]],
            "time_grain": envelope.get("time_grain"),
            "target": spec_args.get("target"),
            "rows": rows[:MAX_ROWS],
            "truncated": len(rows) > MAX_ROWS,
        }
        self.charts.append(chart)
        return ToolResult(
            tool_name=self.name, success=True, content=_summary(chart, spec_args["query"])
        )

    def drain(self) -> List[Dict[str, Any]]:
        """Return the charts shown since the last call, and forget them."""
        charts, self.charts = self.charts, []
        return charts

    async def _kinds(self, entity: str) -> Dict[str, str]:
        if self._measure_kinds is None:
            self._measure_kinds = {}
            result = await self._run_tool("describe_insights", {})
            try:
                schema = json.loads(result.content) if result.success else {}
            except (TypeError, ValueError):
                schema = {}
            for name, entry in (schema.get("entities") or {}).items():
                self._measure_kinds[name] = {
                    m: meta.get("kind", "count") for m, meta in entry.get("measures", {}).items()
                }
        return self._measure_kinds.get(entity, {})

    def _error(self, message: str) -> ToolResult:
        return ToolResult(tool_name=self.name, success=False, error=message)


def _validate(args: Dict[str, Any]) -> Dict[str, Any]:
    query = dict(args.get("query") or {})
    # get_insights takes filters as top-level arguments; accept them nested too.
    query.update(query.pop("filters", None) or {})
    chart_type = args.get("chart_type")
    x, series = args.get("x"), args.get("series")
    y = list(args.get("y") or [])
    group_by = list(query.get("group_by") or [])
    measures = list(query.get("measures") or [])

    if chart_type not in CHART_TYPES:
        raise ValueError(f"chart_type must be one of {list(CHART_TYPES)}")
    if not query.get("entity"):
        raise ValueError("query.entity is required")
    if not y:
        raise ValueError("y must name at least one measure")
    missing = [m for m in y if m not in measures]
    if missing:
        raise ValueError(f"y names {missing}, which the query doesn't request in measures")

    if chart_type == "kpi":
        if group_by or len(y) != 1:
            raise ValueError("kpi needs an empty group_by and exactly one measure in y")
    else:
        expected = [d for d in (x, series) if d]
        if not x or sorted(group_by) != sorted(expected):
            raise ValueError(
                "x (and series, if set) must be exactly the query's group_by dimensions; "
                f"group_by is {group_by}"
            )
    if chart_type == "scatter" and len(y) != 2:
        raise ValueError("scatter needs exactly two measures in y: the x-axis one, then the y-axis")
    if chart_type in ("heat_table", "radar") and len(y) != 1:
        raise ValueError(f"{chart_type} plots exactly one measure")
    if chart_type == "heat_table" and not series:
        raise ValueError("heat_table needs a series dimension for its columns")
    if series and len(y) > 1 and chart_type != "scatter":
        raise ValueError("use either several measures or a series dimension, not both")

    query.setdefault("measures", measures)
    # One row past the cap is enough to know the chart was cut off.
    query["limit"] = min(int(query.get("limit") or MAX_ROWS + 1), MAX_ROWS + 1)
    return {**args, "query": query, "y": y}


SUMMARY_ROWS = 15


def _summary(chart: Dict[str, Any], query: Dict[str, Any]) -> str:
    """What the model needs to describe the chart truthfully: the real labels and values.

    Without them it narrates from nothing, and made-up category names end up beside a
    chart that shows the real ones.
    """
    rows = chart["rows"]
    lines = [_summary_row(chart, row) for row in rows]
    if len(lines) > SUMMARY_ROWS:
        half = SUMMARY_ROWS // 3
        lines = lines[:half] + [f"... {len(lines) - 2 * half} more rows ..."] + lines[-half:]
        # The hidden middle may hold the extremes; without them the model calls the
        # highest value it happened to see "the peak".
        lines += _extremes(chart)
    order = "in time order" if _in_time_order(chart, query) else "in the order shown"
    shown = f"first {len(rows)} rows" if chart["truncated"] else f"{len(rows)} rows"
    return (
        f"Showed the chart '{chart['title']}' ({chart['chart_type']}, {shown}). Its data, "
        f"{order}:\n"
        + "\n".join(lines)
        + "\nDescribe what it shows using these exact names and values. The user sees the "
        "chart and can open its numbers, so don't repeat them as a table."
    )


def _in_time_order(chart: Dict[str, Any], query: Dict[str, Any]) -> bool:
    # get_insights sorts by order_by, else by group_by, so period must be the first key.
    keys = query.get("order_by") or query.get("group_by") or []
    return chart["x"] == "period" and bool(keys) and keys[0] == "period"


def _extremes(chart: Dict[str, Any]) -> List[str]:
    scope = (
        f"Across the first {len(chart['rows'])} rows" if chart["truncated"] else "Across all rows"
    )
    lines = []
    for measure in chart["measures"]:
        key = measure["key"]
        rows = [r for r in chart["rows"] if isinstance(r.get(key), (int, float))]
        if rows:
            low = min(rows, key=lambda r: r[key])
            high = max(rows, key=lambda r: r[key])
            lines.append(
                f"{scope}, lowest {key}: {_summary_row(chart, low)[2:]}; "
                f"highest {key}: {_summary_row(chart, high)[2:]}"
            )
    return lines


def _summary_row(chart: Dict[str, Any], row: Dict[str, Any]) -> str:
    # "(none)" matches how the chart labels a missing value.
    label = " / ".join(
        "(none)" if row.get(d) in (None, "") else str(row.get(d))
        for d in (chart["x"], chart["series"])
        if d
    )
    values = ", ".join(f"{m['key']}={row.get(m['key'])}" for m in chart["measures"])
    return f"- {label}: {values}" if label else f"- {values}"
