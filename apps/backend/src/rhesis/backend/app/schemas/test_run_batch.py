"""Requests and responses for starting a group of test runs at once."""

from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, model_validator

from rhesis.backend.app.schemas.test_set import TestSetExecutionRequest

#: The most runs one group can start: test sets times experiment versions.
MAX_BATCH_RUNS = 50


class BatchExperiment(BaseModel):
    """An experiment version every test set in the group runs with."""

    experiment_id: UUID4
    version: Optional[str] = None


class TestRunBatchCreate(BaseModel):
    """Run several test sets, or every set carrying a tag, against one endpoint."""

    test_set_ids: Optional[List[UUID4]] = Field(default=None, min_length=1)
    test_set_tag: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Run every test set carrying this tag, looked up when the group starts.",
    )
    endpoint_id: UUID4
    experiments: List[BatchExperiment] = Field(
        default_factory=list,
        description="Each test set runs once per experiment version. Empty runs each set once.",
    )
    run_settings: TestSetExecutionRequest = Field(default_factory=TestSetExecutionRequest)

    @model_validator(mode="after")
    def _one_target(self) -> "TestRunBatchCreate":
        if (self.test_set_ids is None) == (self.test_set_tag is None):
            raise ValueError("Send either test_set_ids or test_set_tag.")
        settings = self.run_settings
        # Outputs belong to one test set's run, so reuse needs exactly that one set.
        if settings.reference_test_run_id and len(self.test_set_ids or []) != 1:
            raise ValueError("Reusing outputs needs exactly one test set in test_set_ids.")
        if settings.experiment_id or settings.version or settings.environment:
            raise ValueError("Pick experiments with experiments, not run_settings.")
        return self


class TestRunBatchMember(BaseModel):
    test_set_id: UUID4
    test_set_name: str
    experiment_id: Optional[UUID4] = None
    version: Optional[str] = None
    test_configuration_id: UUID4
    test_run_id: Optional[UUID4] = None
    test_run_name: Optional[str] = None


class TestRunBatchOut(BaseModel):
    """``batch_id`` is empty when the group is a single run."""

    batch_id: Optional[str] = None
    test_set_tag: Optional[str] = None
    members: List[TestRunBatchMember]
