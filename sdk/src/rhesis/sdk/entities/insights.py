"""Client for the generic /insights aggregation endpoint."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rhesis.sdk.clients import APIClient, Endpoints, Methods

ENDPOINT = Endpoints.INSIGHTS


class InsightsResponse(BaseModel):
    entity: str
    dimensions: List[str]
    measures: List[str]
    rows: List[Dict[str, Any]]
    time_grain: Optional[str] = None


class InsightsIdsResponse(BaseModel):
    entity: str
    ids: List[str]


class Insights(BaseModel):
    """One insights query: entity, group_by/measures, filters, and date window.

    Grouping by an entity-backed dimension returns its name and ``<dimension>_id``.
    ``Insights.describe()`` lists what each entity accepts.

    Example:
        >>> insights = Insights(
        ...     entity="test_result",
        ...     group_by=["topic"],
        ...     measures=["count", "pass_rate"],
        ...     filters={"test_run_ids": [run_id]},
        ...     order_by=["pass_rate"],
        ...     limit=5,
        ...     min_count=10,
        ... )
        >>> insights.get()
        >>> insights.ids(outcome="fail")
    """

    entity: str
    group_by: List[str] = Field(default_factory=list)
    measures: List[str] = Field(default_factory=lambda: ["count"])
    filters: Dict[str, List[str]] = Field(default_factory=dict)
    months: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_grain: Optional[str] = None
    order_by: List[str] = Field(default_factory=list)
    limit: Optional[int] = None
    min_count: Optional[int] = None

    @staticmethod
    def describe() -> Dict[str, Any]:
        """Every entity's dimensions, measures and filters, with what each one means."""
        return APIClient().send_request(endpoint=ENDPOINT, method=Methods.GET, url_params="schema")

    def _base_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"entity": self.entity}
        if self.filters:
            params.update(self.filters)
        if self.months is not None:
            params["months"] = self.months
        if self.start_date is not None:
            params["start_date"] = self.start_date
        if self.end_date is not None:
            params["end_date"] = self.end_date
        return params

    def get(self) -> InsightsResponse:
        """Run the query and return the rows."""
        params = self._base_params()
        if self.group_by:
            params["group_by"] = self.group_by
        if self.measures:
            params["measures"] = self.measures
        if self.time_grain is not None:
            params["time_grain"] = self.time_grain
        if self.order_by:
            params["order_by"] = self.order_by
        if self.limit is not None:
            params["limit"] = self.limit
        if self.min_count is not None:
            params["min_count"] = self.min_count

        client = APIClient()
        response = client.send_request(
            endpoint=ENDPOINT,
            method=Methods.GET,
            params=params,
        )
        return InsightsResponse.model_validate(response)

    def ids(self, outcome: str = "all") -> InsightsIdsResponse:
        """Return the IDs (uses the same filters as get()).

        Args:
            outcome: "pass", "fail", or "all". Only "test_result" and
                "metric" support "pass"/"fail".
        """
        params = self._base_params()
        params["outcome"] = outcome

        client = APIClient()
        response = client.send_request(
            endpoint=ENDPOINT,
            method=Methods.GET,
            url_params="ids",
            params=params,
        )
        return InsightsIdsResponse.model_validate(response)
