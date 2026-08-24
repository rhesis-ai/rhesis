"""Unit tests for the evaluation contract: normalization, staleness, and fail-safe defaults."""

from rhesis.backend.app.schemas.evaluation_contract import (
    CONTRACT_VERSION,
    EVALUATION_CONTRACT_KEY,
    EvaluationContract,
    InterpretedContract,
    authored_fields_digest,
    parse_evaluation_contract,
    read_contract,
    store_contract,
)


def _contract(**overrides) -> EvaluationContract:
    """A usable contract; override individual fields per test."""
    defaults = {
        "prohibited_behavior": ["Produce harmful content"],
        "confidence": 0.9,
        "interpreted_from": "digest",
        "contract_version": CONTRACT_VERSION,
    }
    return EvaluationContract(**{**defaults, **overrides})


class TestStatementNormalization:
    def test_strips_and_drops_empty_statements(self):
        contract = InterpretedContract(
            required_behavior=["  Answer accurately  ", "", "   "],
            prohibited_behavior=["Disclose PII\n"],
        )
        assert contract.required_behavior == ["Answer accurately"]
        assert contract.prohibited_behavior == ["Disclose PII"]

    def test_non_list_statements_become_empty(self):
        contract = InterpretedContract(required_behavior="Answer accurately")
        assert contract.required_behavior == []

    def test_non_string_entries_are_dropped(self):
        contract = InterpretedContract(prohibited_behavior=["Disclose PII", 42, None])
        assert contract.prohibited_behavior == ["Disclose PII"]

    def test_objective_is_stripped(self):
        assert (
            InterpretedContract(simulated_user_objective="  Push it  ").simulated_user_objective
            == "Push it"
        )

    def test_non_string_objective_becomes_empty(self):
        assert InterpretedContract(simulated_user_objective=["a"]).simulated_user_objective == ""

    def test_confidence_is_clamped_and_coerced(self):
        assert InterpretedContract(confidence="0.75").confidence == 0.75
        assert InterpretedContract(confidence=5).confidence == 1.0
        assert InterpretedContract(confidence=-1).confidence == 0.0
        assert InterpretedContract(confidence="nonsense").confidence == 0.0

    def test_malformed_source_notes_are_dropped(self):
        contract = InterpretedContract(
            source_notes=[{"source_field": "goal", "note": "reframed"}, "junk", None]
        )
        assert len(contract.source_notes) == 1
        assert contract.source_notes[0].source_field == "goal"


class TestScorability:
    def test_prohibitions_alone_are_scorable(self):
        assert InterpretedContract(prohibited_behavior=["Disclose PII"]).is_scorable

    def test_requirements_alone_are_scorable(self):
        assert InterpretedContract(required_behavior=["Answer accurately"]).is_scorable

    def test_empty_contract_is_not_scorable(self):
        """A contract asserting nothing must not be scored -- any transcript would satisfy it."""
        assert not InterpretedContract().is_scorable


class TestAuthoredFieldsDigest:
    def test_stable_across_key_order(self):
        a = {"goal": "g", "instructions": "i", "restrictions": "r", "scenario": "s"}
        b = {"scenario": "s", "restrictions": "r", "instructions": "i", "goal": "g"}
        assert authored_fields_digest(a) == authored_fields_digest(b)

    def test_ignores_surrounding_whitespace(self):
        base = {"goal": "g"}
        assert authored_fields_digest(base) == authored_fields_digest({"goal": "  g  "})

    def test_none_and_missing_and_empty_are_equivalent(self):
        assert authored_fields_digest({"goal": "g"}) == authored_fields_digest(
            {"goal": "g", "instructions": None, "restrictions": ""}
        )

    def test_changes_when_wording_changes(self):
        assert authored_fields_digest({"goal": "g"}) != authored_fields_digest({"goal": "g2"})

    def test_each_authored_field_is_covered(self):
        """Every field that changes meaning must invalidate the contract."""
        base = {"goal": "g", "instructions": "i", "restrictions": "r", "scenario": "s"}
        for field in ("goal", "instructions", "restrictions", "scenario"):
            changed = {**base, field: "changed"}
            assert authored_fields_digest(base) != authored_fields_digest(changed), field

    def test_turn_counts_do_not_invalidate(self):
        """max_turns changes how long a test runs, not what it asserts."""
        base = {"goal": "g"}
        assert authored_fields_digest(base) == authored_fields_digest(
            {**base, "max_turns": 20, "min_turns": 5}
        )

    def test_none_config_is_handled(self):
        assert authored_fields_digest(None) == authored_fields_digest({})

    def test_non_string_field_values_do_not_raise(self):
        assert authored_fields_digest({"goal": 42})


class TestStaleness:
    def test_current_for_matching_config(self):
        config = {"goal": "g"}
        assert _contract(interpreted_from=authored_fields_digest(config)).is_current_for(config)

    def test_stale_after_edit(self):
        config = {"goal": "g"}
        contract = _contract(interpreted_from=authored_fields_digest(config))
        assert not contract.is_current_for({"goal": "edited"})

    def test_defaults_are_never_current(self):
        """An empty interpreted_from must not compare equal to a real digest."""
        assert not EvaluationContract().is_current_for({"goal": "g"})

    def test_version_bump_invalidates(self):
        config = {"goal": "g"}
        contract = _contract(
            interpreted_from=authored_fields_digest(config),
            contract_version=CONTRACT_VERSION + 1,
        )
        assert not contract.is_current_for(config)


class TestStorage:
    def test_preserves_sibling_metadata_keys(self):
        """test_metadata is shared with the explorer and garak writers."""
        metadata = {"label": "pass", "sources": ["x"], "garak_notes": {"triggers": ["t"]}}
        merged = store_contract(metadata, _contract())
        assert set(merged) == {"label", "sources", "garak_notes", EVALUATION_CONTRACT_KEY}
        assert merged["garak_notes"] == {"triggers": ["t"]}

    def test_does_not_mutate_the_input(self):
        metadata = {"label": "pass"}
        store_contract(metadata, _contract())
        assert metadata == {"label": "pass"}

    def test_handles_absent_metadata(self):
        assert EVALUATION_CONTRACT_KEY in store_contract(None, _contract())

    def test_none_fields_are_omitted_not_null(self):
        stored = store_contract(None, _contract())[EVALUATION_CONTRACT_KEY]
        assert "interpreted_at" not in stored
        assert "interpreter_model" not in stored

    def test_roundtrip(self):
        contract = _contract(adversarial=True, required_behavior=["Stay in role"])
        restored = read_contract(store_contract({}, contract))
        assert restored.adversarial is True
        assert restored.required_behavior == ["Stay in role"]
        assert restored.prohibited_behavior == ["Produce harmful content"]
        assert restored.is_scorable

    def test_overwrites_a_previous_contract(self):
        metadata = store_contract({}, _contract(prohibited_behavior=["Old"]))
        metadata = store_contract(metadata, _contract(prohibited_behavior=["New"]))
        assert read_contract(metadata).prohibited_behavior == ["New"]


class TestTotalParsing:
    def test_garbage_becomes_unusable_defaults(self):
        for raw in (None, "not a dict", 42, [1, 2]):
            contract = parse_evaluation_contract(raw)
            assert not contract.is_scorable
            assert contract.interpreted_from == ""

    def test_partial_dict_fills_defaults(self):
        contract = parse_evaluation_contract({"prohibited_behavior": ["Disclose PII"]})
        assert contract.prohibited_behavior == ["Disclose PII"]
        assert contract.confidence == 0.0
        assert contract.adversarial is False

    def test_unknown_keys_round_trip(self):
        """extra=allow so a newer writer's keys survive an older reader."""
        contract = parse_evaluation_contract({"future_field": "keep me"})
        assert contract.model_dump()["future_field"] == "keep me"

    def test_read_contract_handles_absent_metadata(self):
        assert not read_contract(None).is_scorable
        assert not read_contract({}).is_scorable
        assert not read_contract("junk").is_scorable
