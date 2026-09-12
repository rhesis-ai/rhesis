"""Wire protocol schema tests for the experiment_parameters rename."""

from rhesis.backend.app.services.connector.schemas import ExecuteTestMessage


class TestExecuteTestMessageExperimentParameters:
    """ExecuteTestMessage accepts both wire names."""

    def test_accepts_experiment_parameters_on_wire(self):
        msg = ExecuteTestMessage(
            test_run_id="run-1",
            function_name="fn",
            inputs={"input": "hi"},
            experiment_parameters={"model": "gpt-4o"},
        )
        assert msg.parameters == {"model": "gpt-4o"}
        assert msg.experiment_parameters == {"model": "gpt-4o"}

    def test_accepts_legacy_parameters_on_wire(self):
        msg = ExecuteTestMessage(
            test_run_id="run-1",
            function_name="fn",
            inputs={"input": "hi"},
            parameters={"model": "gpt-4o"},
        )
        assert msg.parameters == {"model": "gpt-4o"}
        assert msg.experiment_parameters == {"model": "gpt-4o"}

    def test_parameters_preferred_when_both_present(self):
        """When both are sent, parameters (the Pydantic field) wins."""
        msg = ExecuteTestMessage(
            test_run_id="run-1",
            function_name="fn",
            inputs={},
            parameters={"model": "from-parameters"},
            experiment_parameters={"model": "from-experiment"},
        )
        assert msg.parameters == {"model": "from-parameters"}

    def test_defaults_to_empty_dict(self):
        msg = ExecuteTestMessage(
            test_run_id="run-1",
            function_name="fn",
            inputs={},
        )
        assert msg.parameters == {}
        assert msg.experiment_parameters == {}
