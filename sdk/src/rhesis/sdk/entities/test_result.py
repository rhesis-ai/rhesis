from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, NoReturn, Optional

from rhesis.sdk.clients import APIClient, Endpoints, Methods

if TYPE_CHECKING:
    from rhesis.sdk.entities.annotation import Annotation
    from rhesis.sdk.entities.file import File
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity
from rhesis.sdk.entities.status import Status

ENDPOINT = Endpoints.TEST_RESULTS


class TestResult(BaseEntity):
    """Test result entity representing execution results from tests.

    Note: This is NOT a pytest test class, despite the 'Test' prefix.
    """

    __test__ = False  # Tell pytest to ignore this class
    endpoint: ClassVar[Endpoints] = ENDPOINT
    test_configuration_id: Optional[str] = None
    test_run_id: Optional[str] = None
    prompt_id: Optional[str] = None
    test_id: Optional[str] = None
    status_id: Optional[str] = None
    status: Optional[Status] = None
    test_output: Optional[Dict[str, Any]] = None
    test_metrics: Optional[Dict[str, Any]] = None
    # Read-only projections of the annotations on this result, embedded by the
    # backend so a grid can render a verdict without a second request.
    last_annotation: Optional[Dict[str, Any]] = None
    matches_annotation: Optional[bool] = None
    annotation_summary: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

    def get_files(self) -> List["File"]:
        """Get all files attached to this test result.

        Returns:
            List of File instances.
        """
        from rhesis.sdk.entities.file import File

        if not self.id:
            raise ValueError("TestResult must have an ID to get files")
        client = APIClient()
        results = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/files",
        )
        return [File.model_validate(r) for r in results]

    def get_annotations(self) -> List["Annotation"]:
        """Get every annotation on this test result.

        Full rows, unlike the ``annotation_summary`` projection above: comments,
        author and resolved state.
        """
        from rhesis.sdk.entities.annotation import AnnotatableEntity, Annotations

        if not self.id:
            raise ValueError("TestResult must have an ID to get annotations")
        return Annotations.for_entity(AnnotatableEntity.TEST_RESULT, self.id)

    def annotate(
        self,
        verdict: str,
        comment: Optional[str] = None,
        *,
        metric: Optional[str] = None,
        turn: Optional[str] = None,
    ) -> "Annotation":
        """Record a human verdict on this result, overriding the automated one.

        ``verdict`` is named rather than looked up: ``"pass"`` or ``"fail"``.

        Target one metric by name or one turn by label to judge just that part and
        leave the rest on their automated verdicts; name neither to judge the
        result as a whole.

            result.annotate("fail", "Cites a policy that does not exist.")
            result.annotate("pass", "Relevant after all.", metric="Answer Relevancy")
        """
        from rhesis.sdk.entities.annotation import AnnotatableEntity, Annotations

        if not self.id:
            raise ValueError("TestResult must have an ID to annotate")
        return Annotations.create(
            AnnotatableEntity.TEST_RESULT,
            self.id,
            verdict,
            comment,
            metric=metric,
            turn=turn,
        )


class TestResults(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestResult

    @classmethod
    def stats(cls, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError(
            "TestResults.stats() has been removed. Use Insights(entity='test_result', ...) "
            "or Insights(entity='metric', ...) directly. See https://docs.rhesis.ai/sdk/insights."
        )
