"""
Tests for metric evaluation functions.

Covers:
- evaluate_single_turn_metrics (renamed from evaluate_prompt_response)
- evaluate_prompt_response backward compatibility alias
- evaluate_multi_turn_metrics for conversational / re-score scenarios
"""

from unittest.mock import MagicMock, patch

from rhesis.backend.app.schemas.evaluation_contract import (
    CONTRACT_VERSION,
    EvaluationContract,
    authored_fields_digest,
    store_contract,
)
from rhesis.backend.jobs.execution.constants import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
    TURN_CONTEXT_KEY,
    TURN_METADATA_KEY,
    TURN_TOOL_CALLS_KEY,
)
from rhesis.backend.jobs.execution.evaluation import (
    evaluate_multi_turn_metrics,
    evaluate_prompt_response,
    evaluate_single_turn_metrics,
)

# ============================================================================
# evaluate_single_turn_metrics tests
# ============================================================================


class TestEvaluateSingleTurnMetrics:
    """Tests for evaluate_single_turn_metrics."""

    def test_returns_evaluation_results(self):
        """Evaluator results are returned from evaluate_single_turn_metrics."""
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {"accuracy": {"score": 0.9, "is_successful": True}}

        result = evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="What is 2+2?",
            expected_response="4",
            context=["math"],
            result={"output": "4"},
            metrics=[{"name": "accuracy", "metric_scope": ["Single-Turn"]}],
        )

        assert result == {"accuracy": {"score": 0.9, "is_successful": True}}
        mock_evaluator.evaluate.assert_called_once()

    def test_extracts_response_with_fallback(self):
        """Response is extracted from result dict via extract_response_with_fallback."""
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {}

        with patch(
            "rhesis.backend.jobs.execution.evaluation.extract_response_with_fallback",
            return_value="extracted text",
        ) as mock_extract:
            evaluate_single_turn_metrics(
                metrics_evaluator=mock_evaluator,
                prompt_content="prompt",
                expected_response="expected",
                context=[],
                result={"output": "raw"},
                metrics=[{"name": "m1", "metric_scope": ["Single-Turn"]}],
            )

        mock_extract.assert_called_once_with({"output": "raw"})
        call_kwargs = mock_evaluator.evaluate.call_args.kwargs
        assert call_kwargs["output_text"] == "extracted text"

    def test_returns_empty_on_evaluation_error(self):
        """Returns empty dict when MetricEvaluator raises an exception."""
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = RuntimeError("LLM unavailable")

        result = evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="p",
            expected_response="e",
            context=[],
            result={"output": "o"},
            metrics=[{"name": "m", "metric_scope": ["Single-Turn"]}],
        )

        assert result == {}

    def test_multi_turn_only_metrics_are_excluded(self):
        """Metrics scoped exclusively to Multi-Turn are not passed to the evaluator."""
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import MetricScope

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {}

        multi_turn_metric = MetricConfig(
            name="conv_metric",
            class_name="ConversationalJudge",
            metric_scope=[MetricScope.MULTI_TURN],
        )

        result = evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="test input",
            expected_response="expected",
            context=[],
            result={"output": "response"},
            metrics=[multi_turn_metric],
        )

        mock_evaluator.evaluate.assert_not_called()
        assert result == {}

    def test_single_turn_metrics_are_not_excluded(self):
        """Metrics scoped to Single-Turn are still passed to the evaluator."""
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import MetricScope

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {"accuracy": {"score": 0.9}}

        single_turn_metric = MetricConfig(
            name="accuracy",
            class_name="NumericJudge",
            metric_scope=[MetricScope.SINGLE_TURN],
        )

        evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="test input",
            expected_response="expected",
            context=[],
            result={"output": "response"},
            metrics=[single_turn_metric],
        )

        mock_evaluator.evaluate.assert_called_once()

    def test_mixed_scope_metric_is_not_excluded(self):
        """A metric scoped to both Single-Turn and Multi-Turn is kept for single-turn."""
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import MetricScope

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {}

        mixed_metric = MetricConfig(
            name="mixed",
            class_name="NumericJudge",
            metric_scope=[MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN],
        )

        evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="test",
            expected_response="",
            context=[],
            result={"output": "response"},
            metrics=[mixed_metric],
        )

        mock_evaluator.evaluate.assert_called_once()

    def test_dict_metric_with_multi_turn_scope_is_excluded(self):
        """A dict metric config with metric_scope=['Multi-Turn'] is excluded (comment #1 fix)."""
        from rhesis.sdk.metrics.base import MetricScope

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {}

        dict_metric = {
            "name": "conv",
            "class_name": "ConversationalJudge",
            "metric_scope": [MetricScope.MULTI_TURN],
        }

        result = evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="test",
            expected_response="",
            context=[],
            result={"output": "response"},
            metrics=[dict_metric],
        )

        mock_evaluator.evaluate.assert_not_called()
        assert result == {}

    def test_bare_string_metric_scope_is_excluded(self):
        """A mis-shaped bare-string metric_scope does not crash, and is dropped.

        filter_configs_by_scope treats anything that isn't a list/tuple/set as
        undeclared scope — same as no scope at all — rather than as "matches
        every scope". MetricConfig validates and rejects bare strings, so this
        scenario can only arrive via a loosely-typed object (e.g. a
        dict-converted mock), but it must not crash and must not silently pass.
        """
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {}

        bad_scope_metric = MagicMock()
        bad_scope_metric.metric_scope = "Multi-Turn"  # bare string, not a list

        result = evaluate_single_turn_metrics(
            metrics_evaluator=mock_evaluator,
            prompt_content="test",
            expected_response="",
            context=[],
            result={"output": "response"},
            metrics=[bad_scope_metric],
        )

        mock_evaluator.evaluate.assert_not_called()
        assert result == {}


# ============================================================================
# Backward compatibility alias tests
# ============================================================================


class TestEvaluatePromptResponseAlias:
    """Tests that evaluate_prompt_response is an alias for evaluate_single_turn_metrics."""

    def test_alias_is_same_function(self):
        """evaluate_prompt_response IS evaluate_single_turn_metrics."""
        assert evaluate_prompt_response is evaluate_single_turn_metrics

    def test_alias_works_correctly(self):
        """evaluate_prompt_response can be called and returns results."""
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = {"m1": {"score": 0.5}}

        result = evaluate_prompt_response(
            metrics_evaluator=mock_evaluator,
            prompt_content="p",
            expected_response="e",
            context=[],
            result={"output": "o"},
            metrics=[{"name": "m1", "metric_scope": ["Single-Turn"]}],
        )

        assert result == {"m1": {"score": 0.5}}


# ============================================================================
# evaluate_multi_turn_metrics tests
# ============================================================================


class TestEvaluateMultiTurnMetrics:
    """Tests for evaluate_multi_turn_metrics."""

    def test_evaluates_conversation_as_single_pair(self):
        """Conversation is reconstructed and evaluated as input/output pair."""
        stored_output = {
            CONVERSATION_SUMMARY_KEY: [
                {PENELOPE_MESSAGE_KEY: "Hello", TARGET_RESPONSE_KEY: "Hi there"},
                {PENELOPE_MESSAGE_KEY: "How are you?", TARGET_RESPONSE_KEY: "I'm fine"},
            ]
        }

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "Greet and check wellness"}
        mock_test.id = "test-1"

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.return_value = {
            "goal_achievement": {"score": 0.8, "is_successful": True}
        }

        # get_test_metrics and prepare_metric_configs are imported locally
        # inside the function, so patch at their source modules
        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        assert result == {"goal_achievement": {"score": 0.8, "is_successful": True}}
        # Check the evaluator was called with the concatenated conversation
        call_kwargs = mock_evaluator_instance.evaluate.call_args.kwargs
        assert call_kwargs["input_text"] == "Greet and check wellness"
        assert "User: Hello" in call_kwargs["output_text"]
        assert "Assistant: Hi there" in call_kwargs["output_text"]
        assert "User: How are you?" in call_kwargs["output_text"]
        assert "Assistant: I'm fine" in call_kwargs["output_text"]

    def test_returns_empty_when_no_metrics(self):
        """Returns empty dict when no metric configs are resolved."""
        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test"}
        mock_test.id = "test-1"

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[],
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output={CONVERSATION_SUMMARY_KEY: []},
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id=None,
                model="gpt-4",
            )

        assert result == {}

    def test_returns_empty_on_evaluation_error(self):
        """Returns empty dict when MetricEvaluator raises an exception."""
        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test"}
        mock_test.id = "test-1"

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.side_effect = RuntimeError("fail")

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output={CONVERSATION_SUMMARY_KEY: []},
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        assert result == {}

    def test_handles_empty_conversation(self):
        """Handles empty conversation_summary gracefully."""
        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test"}
        mock_test.id = "test-1"

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.return_value = {}

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output={CONVERSATION_SUMMARY_KEY: []},
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        call_kwargs = mock_evaluator_instance.evaluate.call_args.kwargs
        assert call_kwargs["output_text"] == ""

    def test_missing_goal_defaults_to_empty(self):
        """When test_configuration has no goal, input_text is empty string."""
        mock_test = MagicMock()
        mock_test.test_configuration = {}
        mock_test.id = "test-1"

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.return_value = {}

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output={CONVERSATION_SUMMARY_KEY: []},
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        call_kwargs = mock_evaluator_instance.evaluate.call_args.kwargs
        assert call_kwargs["input_text"] == ""

    def test_assistant_metadata_in_messages(self):
        """Per-turn metadata from conversation_summary propagates to assistant messages."""
        from rhesis.sdk.metrics.conversational.types import ConversationHistory

        stored_output = {
            CONVERSATION_SUMMARY_KEY: [
                {
                    PENELOPE_MESSAGE_KEY: "Hello",
                    TARGET_RESPONSE_KEY: "Hi",
                    TURN_METADATA_KEY: {"source": "doc1"},
                },
                {
                    PENELOPE_MESSAGE_KEY: "How are you?",
                    TARGET_RESPONSE_KEY: "Fine",
                    # no metadata on this turn
                },
            ]
        }

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test goal"}
        mock_test.id = "test-1"

        captured_history = {}

        def capture_evaluate(**kwargs):
            captured_history["conversation_history"] = kwargs.get("conversation_history")
            return {}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.side_effect = capture_evaluate

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        conv: ConversationHistory = captured_history["conversation_history"]
        assert conv is not None

        metadata_list = conv.get_assistant_metadata()
        assert metadata_list[0] == {"source": "doc1"}
        assert metadata_list[1] is None

    def test_assistant_context_in_messages(self):
        """Per-turn retrieval context from conversation_summary propagates to AssistantMessage.context."""
        from rhesis.sdk.metrics.conversational.types import ConversationHistory

        stored_output = {
            CONVERSATION_SUMMARY_KEY: [
                {
                    PENELOPE_MESSAGE_KEY: "Hello",
                    TARGET_RESPONSE_KEY: "Hi",
                    TURN_CONTEXT_KEY: ["rag chunk 1", "rag chunk 2"],
                },
                {
                    PENELOPE_MESSAGE_KEY: "How are you?",
                    TARGET_RESPONSE_KEY: "Fine",
                    # no context on this turn
                },
            ]
        }

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test goal"}
        mock_test.id = "test-1"

        captured_history = {}

        def capture_evaluate(**kwargs):
            captured_history["conversation_history"] = kwargs.get("conversation_history")
            return {}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.side_effect = capture_evaluate

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        conv: ConversationHistory = captured_history["conversation_history"]
        assert conv is not None

        context_list = conv.get_assistant_context()
        assert context_list[0] == ["rag chunk 1", "rag chunk 2"]
        assert context_list[1] is None

    def test_assistant_context_and_metadata_independent(self):
        """context and metadata are stored in separate fields and returned independently."""
        from rhesis.sdk.metrics.conversational.types import ConversationHistory

        stored_output = {
            CONVERSATION_SUMMARY_KEY: [
                {
                    PENELOPE_MESSAGE_KEY: "Tell me about policy X",
                    TARGET_RESPONSE_KEY: "Policy X covers...",
                    TURN_CONTEXT_KEY: ["policy doc excerpt"],
                    TURN_METADATA_KEY: {"confidence": 0.95},
                },
            ]
        }

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "retrieve policy info"}
        mock_test.id = "test-2"

        captured_history = {}

        def capture_evaluate(**kwargs):
            captured_history["conversation_history"] = kwargs.get("conversation_history")
            return {}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.side_effect = capture_evaluate

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        conv: ConversationHistory = captured_history["conversation_history"]
        assert conv is not None
        assert conv.get_assistant_context() == [["policy doc excerpt"]]
        assert conv.get_assistant_metadata() == [{"confidence": 0.95}]

    def test_build_conversation_history_propagates_tool_calls(self):
        """_build_conversation_history populates AssistantMessage.tool_calls."""
        from rhesis.sdk.metrics.conversational.types import ConversationHistory

        stored_output = {
            CONVERSATION_SUMMARY_KEY: [
                {
                    PENELOPE_MESSAGE_KEY: "Call the search API",
                    TARGET_RESPONSE_KEY: "Found 3 results",
                    TURN_TOOL_CALLS_KEY: [{"name": "search", "arguments": {"q": "policy"}}],
                },
                {
                    PENELOPE_MESSAGE_KEY: "Tell me more",
                    TARGET_RESPONSE_KEY: "Details here",
                },
            ]
        }

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "test tool calls"}
        mock_test.id = "test-tc"

        captured_history = {}

        def capture_evaluate(**kwargs):
            captured_history["conversation_history"] = kwargs.get("conversation_history")
            return {}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.side_effect = capture_evaluate

        with (
            patch(
                "rhesis.backend.jobs.execution.executors.data.get_test_metrics",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "m1"}],
            ),
            patch(
                "rhesis.backend.jobs.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=mock_test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        conv: ConversationHistory = captured_history["conversation_history"]
        assert conv is not None

        tc_list = conv.get_assistant_tool_calls()
        assert tc_list[0] == [{"name": "search", "arguments": {"q": "policy"}}]


class TestEvaluateMultiTurnMetricsContract:
    """Contract handling in the re-score path.

    Unlike ``goal``/``instructions``, which are read live from ``test.test_configuration`` and
    can never be stale, the stored contract is a cached derivative that only gets refreshed by
    a live run's ``ensure_contract`` call. These tests pin down what happens when it's behind
    the test's current wording, and that a stale or unusable contract discards every metric
    rather than falling back to legacy goal-based scoring -- that fallback is the exact bug
    evaluation contracts exist to prevent.
    """

    @staticmethod
    def _test_with_contract(config, contract):
        test = MagicMock()
        test.test_configuration = config
        test.test_metadata = store_contract(None, contract)
        test.id = "test-1"
        return test

    def test_stale_contract_discards_all_metrics(self):
        """A test edited after its last interpretation must not be scored against criteria
        the author no longer wrote."""
        config = {"goal": "Verify the chatbot refuses to leak PII"}
        stale_contract = EvaluationContract(
            prohibited_behavior=["Disclose PII"],
            confidence=0.9,
            interpreted_from=authored_fields_digest({"goal": "An entirely different goal"}),
            contract_version=CONTRACT_VERSION,
        )
        test = self._test_with_contract(config, stale_contract)
        stored_output = {CONVERSATION_SUMMARY_KEY: []}

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.data.get_test_metrics",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "goal_achievement"}],
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        assert result == {}
        # The reason must reach the persisted trace, not just the logs -- MultiTurnRunner.run
        # passes this same dict straight through to create_test_result_record as test_output.
        assert "out of date" in stored_output["error"]

    def test_current_usable_contract_is_passed_through(self):
        """A contract matching the test's current wording is used, not discarded."""
        config = {"goal": "Verify the chatbot refuses to leak PII"}
        current_contract = EvaluationContract(
            prohibited_behavior=["Disclose PII"],
            confidence=0.9,
            interpreted_from=authored_fields_digest(config),
            contract_version=CONTRACT_VERSION,
        )
        test = self._test_with_contract(config, current_contract)
        stored_output = {CONVERSATION_SUMMARY_KEY: []}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.return_value = {
            "goal_achievement": {"is_successful": True, "score": 1.0}
        }

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.data.get_test_metrics",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.evaluation.MetricEvaluator",
                return_value=mock_evaluator_instance,
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        assert result == {"goal_achievement": {"is_successful": True, "score": 1.0}}
        assert mock_evaluator_instance.evaluate.call_args.kwargs["contract"] is not None
        assert "error" not in stored_output

    def test_current_but_low_confidence_contract_discards_all_metrics(self):
        """Freshness alone isn't enough -- an ambiguous-but-current contract still must not
        score. Existing contract_usability behavior; covered here alongside staleness so the
        two failure modes aren't confused with each other."""
        config = {"goal": "Verify the chatbot refuses to leak PII"}
        ambiguous_contract = EvaluationContract(
            prohibited_behavior=["Disclose PII"],
            confidence=0.3,
            interpreted_from=authored_fields_digest(config),
            contract_version=CONTRACT_VERSION,
        )
        test = self._test_with_contract(config, ambiguous_contract)
        stored_output = {CONVERSATION_SUMMARY_KEY: []}

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.data.get_test_metrics",
                return_value=[{"name": "goal_achievement"}],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.metrics.prepare_metric_configs",
                return_value=[{"name": "goal_achievement"}],
            ),
        ):
            result = evaluate_multi_turn_metrics(
                stored_output=stored_output,
                test=test,
                db=MagicMock(),
                organization_id="org-1",
                user_id="user-1",
                model="gpt-4",
            )

        assert result == {}
        # contract_usability's own reason string is already user-facing (see its docstring);
        # reused verbatim rather than replaced with a generic message.
        assert "ambiguous" in stored_output["error"]
