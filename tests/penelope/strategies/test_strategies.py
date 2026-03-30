"""Tests for Penelope exploration strategies."""

import pytest

from rhesis.penelope.strategies import (
    CONTEXT_FIELDS,
    STRATEGY_PERFORMANCE,
    STRATEGY_REGISTRY,
    BoundaryDiscoveryStrategy,
    CapabilityMappingStrategy,
    DomainProbingStrategy,
    ExplorationStrategy,
    PenelopeStrategy,
    StrategyPerformanceRecord,
    get_strategy,
    get_strategy_performance,
    list_strategies,
    record_strategy_run,
)
from rhesis.penelope.strategies.base import (
    _DIFFICULTY_CALIBRATION,
    register_strategy,
)


# -----------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyRegistry:
    """Verify strategies are auto-registered on import."""

    def test_all_three_exploration_strategies_registered(self):
        assert "domain_probing" in STRATEGY_REGISTRY
        assert "capability_mapping" in STRATEGY_REGISTRY
        assert "boundary_discovery" in STRATEGY_REGISTRY

    def test_get_strategy_returns_correct_type(self):
        assert isinstance(get_strategy("domain_probing"), DomainProbingStrategy)
        assert isinstance(get_strategy("capability_mapping"), CapabilityMappingStrategy)
        assert isinstance(get_strategy("boundary_discovery"), BoundaryDiscoveryStrategy)

    def test_get_strategy_raises_on_unknown(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            get_strategy("nonexistent_strategy")

    def test_list_strategies_returns_all(self):
        all_strats = list_strategies()
        assert len(all_strats) >= 3

    def test_list_strategies_filters_by_category(self):
        exploration = list_strategies(category="exploration")
        assert len(exploration) >= 3
        for s in exploration:
            assert s.category == "exploration"

    def test_list_strategies_empty_for_nonexistent_category(self):
        result = list_strategies(category="nonexistent_category_xyz")
        assert result == []


# -----------------------------------------------------------------------
# Hierarchy
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestStrategyHierarchy:
    """Verify the class hierarchy."""

    def test_all_strategies_are_penelope_strategy(self):
        for name in ("domain_probing", "capability_mapping", "boundary_discovery"):
            assert isinstance(get_strategy(name), PenelopeStrategy)

    def test_all_strategies_are_exploration_strategy(self):
        for name in ("domain_probing", "capability_mapping", "boundary_discovery"):
            assert isinstance(get_strategy(name), ExplorationStrategy)

    def test_all_strategies_have_exploration_category(self):
        for name in ("domain_probing", "capability_mapping", "boundary_discovery"):
            assert get_strategy(name).category == "exploration"


# -----------------------------------------------------------------------
# DomainProbingStrategy
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestDomainProbingStrategy:

    @pytest.fixture
    def strategy(self):
        return DomainProbingStrategy()

    def test_name(self, strategy):
        assert strategy.name == "domain_probing"

    def test_description_is_nonempty(self, strategy):
        assert len(strategy.description) > 10

    def test_recommended_max_turns(self, strategy):
        assert strategy.recommended_max_turns == 5

    def test_build_goal_basic(self, strategy):
        goal = strategy.build_goal(target_name="My Bot")
        assert "My Bot" in goal
        assert "domain" in goal.lower() or "purpose" in goal.lower()

    def test_build_goal_with_description(self, strategy):
        goal = strategy.build_goal(
            target_name="My Bot",
            target_description="A travel booking assistant",
        )
        assert "travel booking assistant" in goal

    def test_build_goal_with_additional_context(self, strategy):
        goal = strategy.build_goal(
            target_name="My Bot",
            additional_goal="Pay attention to formality",
        )
        assert "formality" in goal

    def test_build_instructions_basic(self, strategy):
        instructions = strategy.build_instructions(target_name="My Bot")
        assert "My Bot" in instructions
        assert "topic" in instructions.lower()
        assert "persona" in instructions.lower()

    def test_build_instructions_with_previous_findings(self, strategy):
        findings = {
            "domain": "e-commerce",
            "key_topics": ["products", "orders"],
        }
        instructions = strategy.build_instructions(
            target_name="My Bot",
            previous_findings=findings,
        )
        assert "e-commerce" in instructions
        assert "products" in instructions

    def test_format_findings_basic(self, strategy):
        raw = {
            "status": "completed",
            "findings": "The bot covers travel.",
            "conversation": [{"turn": 1, "sent": "Hi", "received": "Hello"}],
            "goal_evaluation": "Goal achieved",
        }
        result = strategy.format_findings(raw)
        assert result["strategy"] == "domain_probing"
        assert result["status"] == "completed"
        assert "domain" in result
        assert "purpose" in result
        assert "persona" in result
        assert "key_topics" in result
        assert "terminology" in result
        assert result["raw_findings_text"] == "The bot covers travel."


# -----------------------------------------------------------------------
# CapabilityMappingStrategy
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestCapabilityMappingStrategy:

    @pytest.fixture
    def strategy(self):
        return CapabilityMappingStrategy()

    def test_name(self, strategy):
        assert strategy.name == "capability_mapping"

    def test_recommended_max_turns(self, strategy):
        assert strategy.recommended_max_turns == 7

    def test_build_goal_incorporates_domain_from_findings(self, strategy):
        goal = strategy.build_goal(
            target_name="My Bot",
            previous_findings={"domain": "healthcare"},
        )
        assert "healthcare" in goal

    def test_build_instructions_with_findings(self, strategy):
        findings = {
            "domain": "finance",
            "capabilities": ["account queries", "transactions"],
        }
        instructions = strategy.build_instructions(
            target_name="My Bot",
            previous_findings=findings,
        )
        assert "finance" in instructions
        assert "account queries" in instructions

    def test_format_findings_has_capability_fields(self, strategy):
        raw = {"status": "completed", "findings": "Can do X and Y."}
        result = strategy.format_findings(raw)
        assert "capabilities" in result
        assert "limitations" in result
        assert "interaction_patterns" in result
        assert "multi_turn_support" in result


# -----------------------------------------------------------------------
# BoundaryDiscoveryStrategy
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestBoundaryDiscoveryStrategy:

    @pytest.fixture
    def strategy(self):
        return BoundaryDiscoveryStrategy()

    def test_name(self, strategy):
        assert strategy.name == "boundary_discovery"

    def test_recommended_max_turns(self, strategy):
        assert strategy.recommended_max_turns == 7

    def test_build_goal_incorporates_domain_and_capabilities(self, strategy):
        goal = strategy.build_goal(
            target_name="My Bot",
            previous_findings={
                "domain": "legal",
                "capabilities": ["contract review", "clause analysis"],
            },
        )
        assert "legal" in goal
        assert "contract review" in goal

    def test_build_instructions_with_findings(self, strategy):
        findings = {
            "domain": "legal",
            "limitations": ["no financial advice"],
        }
        instructions = strategy.build_instructions(
            target_name="My Bot",
            previous_findings=findings,
        )
        assert "legal" in instructions
        assert "no financial advice" in instructions

    def test_format_findings_has_boundary_fields(self, strategy):
        raw = {"status": "completed", "findings": "Refuses off-topic."}
        result = strategy.format_findings(raw)
        assert "refusal_patterns" in result
        assert "domain_boundaries" in result
        assert "safety_guardrails" in result
        assert "boundary_consistency" in result


# -----------------------------------------------------------------------
# Context section (replaces _format_previous_findings)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestContextSection:
    """Test the data-driven _build_context_section helper."""

    @pytest.fixture
    def strategy(self):
        return DomainProbingStrategy()

    def test_none_returns_empty(self, strategy):
        assert strategy._build_context_section(None) == ""

    def test_empty_dict_returns_empty(self, strategy):
        assert strategy._build_context_section({}) == ""

    def test_domain_rendered(self, strategy):
        result = strategy._build_context_section({"domain": "travel"})
        assert "travel" in result

    def test_multiple_fields(self, strategy):
        findings = {
            "domain": "retail",
            "purpose": "product search",
            "key_topics": ["shoes", "clothing"],
            "capabilities": ["search", "recommendations"],
            "limitations": ["no payments"],
            "refusal_patterns": ["off-topic questions"],
            "domain_boundaries": ["only retail"],
        }
        result = strategy._build_context_section(findings)
        assert "retail" in result
        assert "product search" in result
        assert "shoes" in result
        assert "search" in result
        assert "no payments" in result
        assert "off-topic questions" in result
        assert "only retail" in result


# -----------------------------------------------------------------------
# Custom strategy registration
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestRegisterCustomStrategy:
    """Verify that custom strategies can be registered."""

    def test_register_and_retrieve(self):
        class CustomStrategy(ExplorationStrategy):
            strategy_name = "_test_custom"
            strategy_description = "Custom test strategy"
            strategy_max_turns = 3
            findings_fields = {"custom_field": ""}

            def _goal_parts(self, target_name, target_description, previous_findings):
                return [f"Custom goal for {target_name}"]

            def _opening(self, target_name, target_description):
                return f"Custom opening for {target_name}"

            def _body(self, target_name, target_description, previous_findings, **ctx):
                return [f"Custom body for {target_name}"]

        instance = CustomStrategy()
        register_strategy(instance)
        try:
            assert get_strategy("_test_custom") is instance
            assert instance in list_strategies(category="exploration")
            assert instance.format_findings({"status": "ok"})["custom_field"] == ""
        finally:
            STRATEGY_REGISTRY.pop("_test_custom", None)
            STRATEGY_PERFORMANCE.pop("_test_custom", None)


# -----------------------------------------------------------------------
# Novelty filtering (ACD-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestNoveltyFiltering:
    """Test novelty instructions that avoid redundant probing."""

    @pytest.fixture
    def strategy(self):
        return DomainProbingStrategy()

    def test_no_novelty_without_findings(self, strategy):
        result = strategy._build_novelty_instructions(None)
        assert result == ""

    def test_no_novelty_with_empty_findings(self, strategy):
        result = strategy._build_novelty_instructions({})
        assert result == ""

    def test_novelty_skips_known_domain(self, strategy):
        result = strategy._build_novelty_instructions({"domain": "travel"})
        assert "travel" in result
        assert "already established" in result

    def test_novelty_skips_known_topics(self, strategy):
        result = strategy._build_novelty_instructions(
            {"key_topics": ["flights", "hotels"]}
        )
        assert "flights" in result
        assert "hotels" in result
        assert "already mapped" in result

    def test_novelty_skips_known_capabilities(self, strategy):
        result = strategy._build_novelty_instructions(
            {"capabilities": ["booking", "search"]}
        )
        assert "booking" in result
        assert "already confirmed" in result

    def test_novelty_skips_known_refusals(self, strategy):
        result = strategy._build_novelty_instructions(
            {"refusal_patterns": ["financial advice"]}
        )
        assert "financial advice" in result
        assert "documented" in result

    def test_novelty_included_in_instructions(self, strategy):
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"domain": "travel", "key_topics": ["flights"]},
        )
        assert "Novelty filter" in instructions
        assert "already established" in instructions

    def test_novelty_included_in_capability_mapping(self):
        strategy = CapabilityMappingStrategy()
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"capabilities": ["search", "booking"]},
        )
        assert "Novelty filter" in instructions

    def test_novelty_included_in_boundary_discovery(self):
        strategy = BoundaryDiscoveryStrategy()
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"refusal_patterns": ["off-topic"]},
        )
        assert "Novelty filter" in instructions


# -----------------------------------------------------------------------
# Difficulty calibration (ACD-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestDifficultyCalibration:
    """Test difficulty adaptation instructions."""

    def test_calibration_constant_exists(self):
        assert "Difficulty calibration" in _DIFFICULTY_CALIBRATION
        assert "detailed, confident" in _DIFFICULTY_CALIBRATION
        assert "vague or generic" in _DIFFICULTY_CALIBRATION
        assert "partially answers" in _DIFFICULTY_CALIBRATION

    def test_calibration_in_domain_probing(self):
        instructions = DomainProbingStrategy().build_instructions(target_name="Bot")
        assert "Difficulty calibration" in instructions

    def test_calibration_in_capability_mapping(self):
        instructions = CapabilityMappingStrategy().build_instructions(target_name="Bot")
        assert "Difficulty calibration" in instructions

    def test_calibration_in_boundary_discovery(self):
        instructions = BoundaryDiscoveryStrategy().build_instructions(target_name="Bot")
        assert "Difficulty calibration" in instructions


# -----------------------------------------------------------------------
# Domain decomposition (AutoRedTeamer-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestDomainDecomposition:
    """Test risk decomposition in domain probing."""

    @pytest.fixture
    def strategy(self):
        return DomainProbingStrategy()

    def test_five_dimensions_in_instructions(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "Scope" in instructions
        assert "Depth" in instructions
        assert "Persona" in instructions
        assert "Terminology" in instructions
        assert "Adjacent Domains" in instructions

    def test_decomposition_section_header(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "Decomposition" in instructions
        assert "five dimensions" in instructions

    def test_dimensions_class_attribute(self, strategy):
        assert len(strategy.dimensions) == 5
        keys = [k for k, _ in strategy.dimensions]
        assert "scope" in keys
        assert "adjacent_domains" in keys

    def test_format_findings_includes_depth_and_adjacent(self, strategy):
        raw = {"status": "completed", "findings": "Test"}
        result = strategy.format_findings(raw)
        assert "depth_assessment" in result
        assert "adjacent_domains" in result


# -----------------------------------------------------------------------
# Capability difficulty escalation (ACD-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestCapabilityDifficultyEscalation:

    @pytest.fixture
    def strategy(self):
        return CapabilityMappingStrategy()

    def test_query_type_taxonomy_in_instructions(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        lower = instructions.lower()
        assert "factual" in lower
        assert "procedural" in lower
        assert "analytical" in lower
        assert "multi turn" in lower or "multi_turn" in lower
        assert "edge case" in lower or "edge_case" in lower

    def test_progressive_escalation_in_instructions(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "Baseline probe" in instructions
        assert "Stress test" in instructions
        assert "Record the ceiling" in instructions

    def test_known_capabilities_trigger_skip_guidance(self, strategy):
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"capabilities": ["factual", "multi_turn"]},
        )
        assert "already confirmed" in instructions

    def test_format_findings_includes_ceilings(self, strategy):
        raw = {"status": "completed", "findings": "Test"}
        result = strategy.format_findings(raw)
        assert "capability_ceilings" in result
        assert "query_type_coverage" in result


# -----------------------------------------------------------------------
# Boundary probe-classify-verify (AutoRedTeamer-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestBoundaryProbeClassifyVerify:

    @pytest.fixture
    def strategy(self):
        return BoundaryDiscoveryStrategy()

    def test_five_boundary_dimensions_in_instructions(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "Domain Edge" in instructions
        assert "Sensitivity" in instructions
        assert "Capability Limit" in instructions
        assert "Instruction Conflict" in instructions
        assert "Consistency" in instructions

    def test_probe_classify_verify_cycle(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "Probe" in instructions
        assert "Classify" in instructions
        assert "Verify" in instructions
        assert "Hard boundary" in instructions
        assert "Soft boundary" in instructions

    def test_domain_edge_uses_known_domain(self, strategy):
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"domain": "healthcare"},
        )
        assert "healthcare" in instructions
        assert "one step outside" in instructions

    def test_capability_limit_uses_known_capabilities(self, strategy):
        instructions = strategy.build_instructions(
            target_name="Bot",
            previous_findings={"capabilities": ["diagnosis", "treatment info"]},
        )
        assert "diagnosis" in instructions

    def test_consistency_dimension_requires_two_turns(self, strategy):
        instructions = strategy.build_instructions(target_name="Bot")
        assert "at least two turns" in instructions

    def test_format_findings_includes_hard_soft(self, strategy):
        raw = {"status": "completed", "findings": "Test"}
        result = strategy.format_findings(raw)
        assert "hard_boundaries" in result
        assert "soft_boundaries" in result


# -----------------------------------------------------------------------
# Performance tracking (AutoRedTeamer-inspired)
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestPerformanceTracking:

    def test_performance_record_initial_state(self):
        record = StrategyPerformanceRecord()
        assert record.runs == 0
        assert record.avg_findings_per_run == 0.0
        assert record.goal_achievement_rate == 0.0

    def test_record_run_increments_counters(self):
        record = StrategyPerformanceRecord()
        record.record_run({
            "goal_achieved": True,
            "turns_used": 5,
            "domain": "travel",
            "capabilities": ["booking", "search"],
        })
        assert record.runs == 1
        assert record.goal_achieved_count == 1
        assert record.total_turns_used == 5
        assert record.total_findings == 3  # domain + 2 capabilities

    def test_record_run_skips_metadata_fields(self):
        """Verify PERF_SKIP_KEYS are not counted as findings."""
        record = StrategyPerformanceRecord()
        record.record_run({
            "strategy": "domain_probing",
            "status": "completed",
            "raw_findings": "some text",
            "raw_findings_text": "more text",
            "conversation_summary": [{"turn": 1}],
            "goal_evaluation": "achieved",
            "domain": "travel",
        })
        assert record.total_findings == 1  # only "domain"

    def test_multiple_runs_accumulate(self):
        record = StrategyPerformanceRecord()
        record.record_run({"goal_achieved": True, "turns_used": 3, "domain": "travel"})
        record.record_run({"goal_achieved": False, "turns_used": 5, "purpose": "booking"})
        assert record.runs == 2
        assert record.goal_achievement_rate == 0.5
        assert record.total_turns_used == 8

    def test_to_dict(self):
        record = StrategyPerformanceRecord()
        record.record_run({"goal_achieved": True, "turns_used": 3, "domain": "x"})
        d = record.to_dict()
        assert d["runs"] == 1
        assert d["goal_achievement_rate"] == 1.0
        assert "avg_findings_per_run" in d

    def test_record_strategy_run_function(self):
        initial = STRATEGY_PERFORMANCE.get("domain_probing")
        initial_count = initial.runs if initial else 0
        record_strategy_run("domain_probing", {
            "goal_achieved": True,
            "turns_used": 4,
            "domain": "test",
        })
        assert STRATEGY_PERFORMANCE["domain_probing"].runs == initial_count + 1

    def test_get_strategy_performance_all(self):
        stats = get_strategy_performance()
        assert "domain_probing" in stats
        assert "capability_mapping" in stats
        assert "boundary_discovery" in stats

    def test_get_strategy_performance_single(self):
        stats = get_strategy_performance("domain_probing")
        assert "domain_probing" in stats
        assert "runs" in stats["domain_probing"]


# -----------------------------------------------------------------------
# Data-driven CONTEXT_FIELDS
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestContextFieldsTable:
    """Verify the CONTEXT_FIELDS table drives context + novelty."""

    def test_context_fields_has_entries(self):
        assert len(CONTEXT_FIELDS) >= 8

    def test_each_entry_is_3_tuple(self):
        for entry in CONTEXT_FIELDS:
            assert len(entry) == 3
            key, label, directive = entry
            assert isinstance(key, str)
            assert isinstance(label, str)
            assert directive is None or isinstance(directive, str)

    def test_novelty_only_for_fields_with_directive(self):
        strategy = DomainProbingStrategy()
        all_keys = {k for k, _, _ in CONTEXT_FIELDS}
        keys_with_directive = {k for k, _, d in CONTEXT_FIELDS if d is not None}

        findings = {k: "test_value" for k in all_keys}
        for k in all_keys:
            if k in ("key_topics", "capabilities", "limitations",
                     "refusal_patterns", "domain_boundaries",
                     "hard_boundaries", "soft_boundaries"):
                findings[k] = ["test_item"]

        novelty = strategy._build_novelty_instructions(findings)
        for key, _, directive in CONTEXT_FIELDS:
            if directive is not None:
                assert directive[:20] in novelty, (
                    f"Expected directive for '{key}' in novelty output"
                )


# -----------------------------------------------------------------------
# Template method integration
# -----------------------------------------------------------------------


@pytest.mark.unit
class TestTemplateMethodIntegration:
    """Verify the template methods assemble correctly."""

    @pytest.mark.parametrize("strategy_cls", [
        DomainProbingStrategy,
        CapabilityMappingStrategy,
        BoundaryDiscoveryStrategy,
    ])
    def test_instructions_contain_all_sections(self, strategy_cls):
        strategy = strategy_cls()
        instructions = strategy.build_instructions(
            target_name="TestBot",
            previous_findings={"domain": "travel", "capabilities": ["search"]},
        )
        assert "TestBot" in instructions
        assert "Difficulty calibration" in instructions
        assert "Novelty filter" in instructions
        assert "Context from previous exploration" in instructions

    @pytest.mark.parametrize("strategy_cls", [
        DomainProbingStrategy,
        CapabilityMappingStrategy,
        BoundaryDiscoveryStrategy,
    ])
    def test_goal_includes_additional_goal(self, strategy_cls):
        strategy = strategy_cls()
        goal = strategy.build_goal(
            target_name="TestBot",
            additional_goal="Focus on edge cases",
        )
        assert "Focus on edge cases" in goal

    @pytest.mark.parametrize("strategy_cls", [
        DomainProbingStrategy,
        CapabilityMappingStrategy,
        BoundaryDiscoveryStrategy,
    ])
    def test_format_findings_produces_correct_keys(self, strategy_cls):
        strategy = strategy_cls()
        raw = {"status": "completed", "findings": "some findings"}
        result = strategy.format_findings(raw)
        assert result["strategy"] == strategy.name
        assert result["status"] == "completed"
        for field_key in strategy.findings_fields:
            assert field_key in result
        assert result["raw_findings_text"] == "some findings"

    @pytest.mark.parametrize("strategy_cls", [
        DomainProbingStrategy,
        CapabilityMappingStrategy,
        BoundaryDiscoveryStrategy,
    ])
    def test_dimensions_rendered_in_instructions(self, strategy_cls):
        strategy = strategy_cls()
        instructions = strategy.build_instructions(target_name="Bot")
        for key, _ in strategy.dimensions:
            label = key.replace("_", " ").title()
            assert label in instructions, f"Expected '{label}' in instructions"
