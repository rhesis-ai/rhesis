#!/usr/bin/env python3
"""
Test scenarios for Research Assistant agent.

This script runs various test scenarios against the Research Assistant API endpoint
to demonstrate the composable tool chaining capabilities.

Usage:
    # Make sure the server is running first:
    # uv run python -m research_assistant

    # Then run the tests:
    uv run python examples/test_scenarios.py

    # Run specific scenario:
    uv run python examples/test_scenarios.py --scenario safety_assessment

    # Run all scenarios:
    uv run python examples/test_scenarios.py --all
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass

import requests

# API Configuration
BASE_URL = "http://localhost:8888"
CHAT_ENDPOINT = f"{BASE_URL}/chat"


@dataclass
class TestScenario:
    """A test scenario definition."""

    name: str
    description: str
    query: str
    expected_tool_layers: list[str]  # Expected layers to be called
    category: str


# =============================================================================
# TEST SCENARIOS
# =============================================================================

SCENARIOS = [
    # ---------------------------------------------------------------------
    # Safety Assessment Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="safety_assessment",
        description="Comprehensive safety assessment for a drug target",
        query=(
            "Perform a comprehensive safety assessment for BRAF as a melanoma target "
            "and provide recommendations for risk mitigation."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="safety",
    ),
    TestScenario(
        name="safety_comparison",
        description="Compare safety profiles of multiple targets",
        query=(
            "Compare the safety profiles of JAK1, JAK2, and JAK3 inhibitors for "
            "rheumatoid arthritis treatment. Which has the best safety profile?"
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="safety",
    ),
    # ---------------------------------------------------------------------
    # Target Prioritization Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="target_ranking",
        description="Rank targets based on multiple criteria",
        query=(
            "Rank these 5 targets based on druggability and safety profile: "
            "EGFR, KRAS, CDK4, PD-1, HER2. Provide a detailed comparison."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="target_prioritization",
    ),
    TestScenario(
        name="target_dossier",
        description="Generate comprehensive target dossier",
        query=(
            "Generate a target dossier for PCSK9, focusing on cardiovascular indications. "
            "Include biology, validation, safety, and competitive landscape."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="target_prioritization",
    ),
    # ---------------------------------------------------------------------
    # Competitive Landscape Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="competitive_analysis",
        description="Analyze competitive landscape for a therapeutic area",
        query="Summarize the competitive landscape for biostimulants in Brazil.",
        expected_tool_layers=["retrieval", "analysis"],
        category="competitive",
    ),
    TestScenario(
        name="market_and_patent",
        description="Combined market and patent analysis",
        query=(
            "Analyze the market opportunity and patent landscape for GLP-1 receptor "
            "agonists in obesity treatment. What are the key opportunities and risks?"
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="competitive",
    ),
    # ---------------------------------------------------------------------
    # Knowledge Gap Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="knowledge_gaps",
        description="Identify knowledge gaps and suggest experiments",
        query=(
            "What are the knowledge gaps for KRAS G12C as a lung cancer target? "
            "Suggest experiments to address them."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="knowledge_gaps",
    ),
    TestScenario(
        name="validation_gaps",
        description="Identify target validation gaps",
        query=(
            "For the target TREM2 in Alzheimer's disease, identify what validation "
            "evidence is missing and propose experiments to fill these gaps."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="knowledge_gaps",
    ),
    # ---------------------------------------------------------------------
    # Synthesis Route Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="synthesis_routes",
        description="Find optimal synthesis routes for a compound",
        query=(
            "What are the most cost-effective synthesis routes for ibuprofen? "
            "Compare routes based on cost, yield, and environmental impact."
        ),
        expected_tool_layers=["retrieval", "analysis"],
        category="synthesis",
    ),
    TestScenario(
        name="compound_optimization",
        description="Compound analysis and optimization",
        query=(
            "Analyze the compound properties of vemurafenib and suggest routes "
            "for synthesis optimization focusing on scalability."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="synthesis",
    ),
    # ---------------------------------------------------------------------
    # Literature & Evidence Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="literature_review",
        description="Literature search and evidence synthesis",
        query=(
            "Search for recent publications on CAR-T cell therapy resistance mechanisms "
            "and synthesize the key findings."
        ),
        expected_tool_layers=["retrieval", "analysis"],
        category="literature",
    ),
    TestScenario(
        name="evidence_summary",
        description="Summarize evidence for a hypothesis",
        query=(
            "What is the evidence supporting the role of the gut microbiome in "
            "Parkinson's disease? Summarize the key findings and gaps."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="literature",
    ),
    # ---------------------------------------------------------------------
    # Multi-Turn Conversation Scenarios
    # ---------------------------------------------------------------------
    TestScenario(
        name="follow_up_refinement",
        description="Multi-turn with refinement (Part 1)",
        query=(
            "Analyze the druggability of BTK for B-cell malignancies. "
            "What are the main considerations?"
        ),
        expected_tool_layers=["retrieval", "analysis"],
        category="multi_turn",
    ),
    TestScenario(
        name="complex_multi_step",
        description="Complex analysis requiring multiple tool chains",
        query=(
            "I need a comprehensive analysis of ALK as a lung cancer target. "
            "Include safety data, druggability assessment, current patent landscape, "
            "and competitive positioning. Identify gaps and recommend next steps."
        ),
        expected_tool_layers=["retrieval", "analysis", "synthesis"],
        category="complex",
    ),
]


# =============================================================================
# TEST EXECUTION
# =============================================================================


def check_server_health() -> bool:
    """Check if the server is running and healthy."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        return data.get("status") == "healthy" and data.get("agent_initialized", False)
    except requests.exceptions.RequestException:
        return False


def run_scenario(
    scenario: TestScenario,
    conversation_id: str | None = None,
    verbose: bool = True,
) -> dict:
    """Run a single test scenario."""
    if verbose:
        print(f"\n{'=' * 70}")
        print(f"Scenario: {scenario.name}")
        print(f"Category: {scenario.category}")
        print(f"Description: {scenario.description}")
        print(f"{'=' * 70}")
        print(f"\nQuery: {scenario.query[:100]}...")

    payload = {"message": scenario.query}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    start_time = time.time()
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "scenario": scenario.name,
        }

    elapsed = time.time() - start_time

    # Analyze results
    tools_called = data.get("tools_called", [])
    tool_chain = data.get("tool_chain", "")
    layers_used = set(t.get("tool_layer", "unknown") for t in tools_called)

    # Check if expected layers were used
    expected_layers = set(scenario.expected_tool_layers)
    layers_match = expected_layers.issubset(layers_used)

    result = {
        "success": True,
        "scenario": scenario.name,
        "category": scenario.category,
        "elapsed_seconds": round(elapsed, 2),
        "tools_called_count": len(tools_called),
        "tool_chain": tool_chain,
        "layers_used": list(layers_used),
        "expected_layers": scenario.expected_tool_layers,
        "layers_match": layers_match,
        "conversation_id": data.get("conversation_id"),
        "response_preview": data.get("response", "")[:200],
    }

    if verbose:
        print(f"\nTool Chain: {tool_chain}")
        print(f"\nTools Called ({len(tools_called)}):")
        for t in tools_called:
            print(f"  [{t.get('tool_layer', 'unknown').upper()}] {t['tool_name']}")
        print(f"\nLayers used: {', '.join(layers_used)}")
        print(f"Expected layers: {', '.join(expected_layers)}")
        print(f"Layers match: {'✓' if layers_match else '✗'}")
        print(f"\nElapsed time: {elapsed:.2f}s")
        print(f"\nResponse preview:\n{data.get('response', '')[:300]}...")

    return result


def run_multi_turn_btk_analysis(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 1: BTK Target Analysis with Refinement.

    Tests: Initial analysis → Safety focus with filter → Strategic recommendations
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 1: BTK Target Analysis with Refinement")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Initial analysis
    turn1_query = (
        "Analyze the druggability of BTK for B-cell malignancies. What are the main considerations?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="btk_turn_1",
            description="Initial BTK analysis",
            query=turn1_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: Follow-up with refinement
    turn2_query = (
        "Based on your analysis, what are the key safety concerns? "
        "Exclude any data from studies before 2015."
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="btk_turn_2",
            description="Safety focus with exclusion",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Request recommendations
    turn3_query = (
        "Given the druggability and safety profile, provide strategic recommendations "
        "for pursuing BTK as a target. What experiments should be prioritized?"
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="btk_turn_3",
            description="Strategic recommendations",
            query=turn3_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    return results


def run_multi_turn_competitive_deep_dive(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 2: Competitive Landscape Deep Dive.

    Tests: Market overview → Competitor focus → Patent analysis → Strategic positioning
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 2: Competitive Landscape Deep Dive")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Market overview
    turn1_query = (
        "Give me an overview of the SGLT2 inhibitors market for type 2 diabetes. "
        "What's the current market size and who are the key players?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="competitive_turn_1",
            description="Market overview",
            query=turn1_query,
            expected_tool_layers=["retrieval"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: Focus on specific competitor
    turn2_query = (
        "Tell me more about the pipeline for SGLT2 inhibitors. "
        "What new indications are being explored beyond diabetes?"
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="competitive_turn_2",
            description="Pipeline analysis",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Patent landscape
    turn3_query = (
        "What does the patent landscape look like for SGLT2 inhibitors? "
        "When do key patents expire and what's the freedom to operate?"
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="competitive_turn_3",
            description="Patent landscape",
            query=turn3_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    # Turn 4: Strategic recommendations
    turn4_query = (
        "Based on all this analysis, what are the strategic opportunities for us? "
        "Should we pursue a me-too approach or focus on differentiation?"
    )
    if verbose:
        print(f"\n[Turn 4] Query: {turn4_query}")

    result4 = run_scenario(
        TestScenario(
            name="competitive_turn_4",
            description="Strategic recommendations",
            query=turn4_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result4)

    return results


def run_multi_turn_target_validation(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 3: Target Validation Journey.

    Tests: Target info → Literature evidence → Gaps → Experimental plan
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 3: Target Validation Journey")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Initial target info
    turn1_query = (
        "Tell me about TREM2 as a potential target for Alzheimer's disease. "
        "What do we know about its biology and disease association?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="validation_turn_1",
            description="Target biology",
            query=turn1_query,
            expected_tool_layers=["retrieval"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: Literature evidence
    turn2_query = (
        "What's the genetic evidence supporting TREM2 in Alzheimer's? "
        "Search the literature for key publications on TREM2 variants."
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="validation_turn_2",
            description="Genetic evidence",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Identify gaps
    turn3_query = (
        "Based on what we've discussed, what are the key validation gaps for TREM2? "
        "What evidence is missing that we'd need before committing to this target?"
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="validation_turn_3",
            description="Identify gaps",
            query=turn3_query,
            expected_tool_layers=["analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    # Turn 4: Experimental plan
    turn4_query = (
        "Design an experimental plan to address the top 3 validation gaps. "
        "Prioritize by impact and feasibility."
    )
    if verbose:
        print(f"\n[Turn 4] Query: {turn4_query}")

    result4 = run_scenario(
        TestScenario(
            name="validation_turn_4",
            description="Experimental plan",
            query=turn4_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result4)

    return results


def run_multi_turn_compound_optimization(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 4: Compound Optimization Workflow.

    Tests: Compound analysis → ADMET focus → Synthesis routes → Optimization strategy
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 4: Compound Optimization Workflow")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Initial compound analysis
    turn1_query = (
        "Analyze the properties of our lead compound targeting CDK4/6. "
        "It has the structure similar to palbociclib. What are its key characteristics?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="compound_turn_1",
            description="Compound analysis",
            query=turn1_query,
            expected_tool_layers=["retrieval"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: ADMET focus
    turn2_query = (
        "What are the main ADMET liabilities for this compound class? "
        "Focus on the metabolic stability and potential drug-drug interactions."
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="compound_turn_2",
            description="ADMET analysis",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Synthesis routes
    turn3_query = (
        "What are the most cost-effective synthesis routes for scaling up this compound? "
        "We need to produce 100kg for Phase 2 trials."
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="compound_turn_3",
            description="Synthesis planning",
            query=turn3_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    # Turn 4: Optimization recommendations
    turn4_query = (
        "Given the ADMET issues and synthesis considerations, "
        "what structural modifications would you recommend to optimize the compound?"
    )
    if verbose:
        print(f"\n[Turn 4] Query: {turn4_query}")

    result4 = run_scenario(
        TestScenario(
            name="compound_turn_4",
            description="Optimization strategy",
            query=turn4_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result4)

    return results


def run_multi_turn_safety_escalation(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 5: Safety Signal Investigation.

    Tests: Initial safety query → Deep dive → Literature check → Risk mitigation
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 5: Safety Signal Investigation")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Initial safety concern
    turn1_query = (
        "We've seen some liver enzyme elevations in our Phase 1 trial with a new "
        "MEK inhibitor. What's known about hepatotoxicity with MEK inhibitors?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="safety_turn_1",
            description="Initial safety query",
            query=turn1_query,
            expected_tool_layers=["retrieval"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: Deep dive into mechanism
    turn2_query = (
        "What's the mechanism behind MEK inhibitor hepatotoxicity? "
        "Is it on-target or off-target? What's the dose relationship?"
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="safety_turn_2",
            description="Mechanism deep dive",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Check competitor experience
    turn3_query = (
        "How have other MEK inhibitors in development or on the market dealt with this? "
        "What monitoring strategies are used?"
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="safety_turn_3",
            description="Competitor comparison",
            query=turn3_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    # Turn 4: Risk mitigation plan
    turn4_query = (
        "Based on all this, develop a risk mitigation strategy for our Phase 2 trial. "
        "Include monitoring protocols and stopping rules."
    )
    if verbose:
        print(f"\n[Turn 4] Query: {turn4_query}")

    result4 = run_scenario(
        TestScenario(
            name="safety_turn_4",
            description="Risk mitigation plan",
            query=turn4_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result4)

    return results


def run_multi_turn_pivot_scenario(verbose: bool = True) -> list[dict]:
    """
    Multi-turn scenario 6: Analysis Pivot.

    Tests: Start with one target → Discover issues → Pivot to alternative → Compare
    """
    if verbose:
        print(f"\n{'=' * 70}")
        print("Multi-Turn Scenario 6: Analysis Pivot")
        print(f"{'=' * 70}")

    results = []

    # Turn 1: Initial target analysis
    turn1_query = (
        "Analyze MET as a target for non-small cell lung cancer. "
        "Is it a good target for small molecule inhibition?"
    )
    if verbose:
        print(f"\n[Turn 1] Query: {turn1_query}")

    result1 = run_scenario(
        TestScenario(
            name="pivot_turn_1",
            description="Initial MET analysis",
            query=turn1_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        verbose=verbose,
    )
    results.append(result1)

    if not result1.get("success"):
        return results

    conversation_id = result1.get("conversation_id")

    # Turn 2: Discover competitive saturation
    turn2_query = (
        "The competitive landscape seems crowded. What about targeting MET via "
        "alternative modalities like degraders or antibodies instead?"
    )
    if verbose:
        print(f"\n[Turn 2] Query: {turn2_query}")

    result2 = run_scenario(
        TestScenario(
            name="pivot_turn_2",
            description="Alternative modalities",
            query=turn2_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result2)

    # Turn 3: Pivot to related target
    turn3_query = (
        "Actually, let's pivot. What about HGF, the MET ligand, as an alternative target? "
        "Compare targeting HGF vs MET directly."
    )
    if verbose:
        print(f"\n[Turn 3] Query: {turn3_query}")

    result3 = run_scenario(
        TestScenario(
            name="pivot_turn_3",
            description="Pivot to HGF",
            query=turn3_query,
            expected_tool_layers=["retrieval", "analysis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result3)

    # Turn 4: Final recommendation
    turn4_query = (
        "Given everything we've discussed about MET and HGF, what's your final "
        "recommendation for the best approach to target this pathway?"
    )
    if verbose:
        print(f"\n[Turn 4] Query: {turn4_query}")

    result4 = run_scenario(
        TestScenario(
            name="pivot_turn_4",
            description="Final recommendation",
            query=turn4_query,
            expected_tool_layers=["analysis", "synthesis"],
            category="multi_turn",
        ),
        conversation_id=conversation_id,
        verbose=verbose,
    )
    results.append(result4)

    return results


# Registry of all multi-turn scenarios
MULTI_TURN_SCENARIOS = {
    "btk_analysis": {
        "name": "BTK Target Analysis",
        "description": "Initial analysis → Safety focus → Recommendations",
        "runner": run_multi_turn_btk_analysis,
    },
    "competitive_deep_dive": {
        "name": "Competitive Deep Dive",
        "description": "Market → Pipeline → Patents → Strategy",
        "runner": run_multi_turn_competitive_deep_dive,
    },
    "target_validation": {
        "name": "Target Validation Journey",
        "description": "Biology → Evidence → Gaps → Experiments",
        "runner": run_multi_turn_target_validation,
    },
    "compound_optimization": {
        "name": "Compound Optimization",
        "description": "Properties → ADMET → Synthesis → Optimization",
        "runner": run_multi_turn_compound_optimization,
    },
    "safety_investigation": {
        "name": "Safety Signal Investigation",
        "description": "Signal → Mechanism → Comparison → Mitigation",
        "runner": run_multi_turn_safety_escalation,
    },
    "analysis_pivot": {
        "name": "Analysis Pivot",
        "description": "Target A → Issues → Pivot to B → Compare",
        "runner": run_multi_turn_pivot_scenario,
    },
}


def run_all_multi_turn_scenarios(verbose: bool = True) -> list[dict]:
    """Run all multi-turn scenarios."""
    all_results = []
    for scenario_id, scenario_info in MULTI_TURN_SCENARIOS.items():
        if verbose:
            print(f"\n\n{'#' * 70}")
            print(f"# Running: {scenario_info['name']}")
            print(f"# {scenario_info['description']}")
            print(f"{'#' * 70}")
        results = scenario_info["runner"](verbose=verbose)
        all_results.extend(results)
    return all_results


def print_summary(results: list[dict]) -> None:
    """Print a summary of all test results."""
    print(f"\n{'=' * 70}")
    print("TEST SUMMARY")
    print(f"{'=' * 70}")

    total = len(results)
    successful = sum(1 for r in results if r.get("success"))
    layers_matched = sum(1 for r in results if r.get("layers_match"))

    print(f"\nTotal scenarios: {total}")
    print(f"Successful: {successful}/{total}")
    print(f"Layers matched: {layers_matched}/{total}")

    # Group by category
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "tools": 0, "time": 0}
        categories[cat]["total"] += 1
        if r.get("success"):
            categories[cat]["success"] += 1
            categories[cat]["tools"] += r.get("tools_called_count", 0)
            categories[cat]["time"] += r.get("elapsed_seconds", 0)

    print("\nBy Category:")
    print("-" * 50)
    for cat, stats in sorted(categories.items()):
        avg_tools = stats["tools"] / stats["success"] if stats["success"] else 0
        avg_time = stats["time"] / stats["success"] if stats["success"] else 0
        print(
            f"  {cat}: {stats['success']}/{stats['total']} passed, "
            f"avg {avg_tools:.1f} tools, avg {avg_time:.1f}s"
        )

    # List failures
    failures = [r for r in results if not r.get("success")]
    if failures:
        print("\nFailed Scenarios:")
        for f in failures:
            print(f"  - {f['scenario']}: {f.get('error', 'Unknown error')}")

    # List layer mismatches
    mismatches = [r for r in results if r.get("success") and not r.get("layers_match")]
    if mismatches:
        print("\nLayer Mismatches:")
        for m in mismatches:
            print(f"  - {m['scenario']}: expected {m['expected_layers']}, got {m['layers_used']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Research Assistant test scenarios")
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run a specific single-turn scenario by name",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Run all scenarios in a category",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all scenarios (single-turn and multi-turn)",
    )
    parser.add_argument(
        "--multi-turn",
        type=str,
        nargs="?",
        const="all",
        help="Run multi-turn scenarios. Optionally specify which one.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available scenarios",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )
    args = parser.parse_args()

    # List scenarios
    if args.list:
        print("Single-Turn Scenarios:")
        print("-" * 50)
        for s in SCENARIOS:
            print(f"  {s.name} ({s.category})")
            print(f"    {s.description}")
        print("\nCategories:", ", ".join(sorted(set(s.category for s in SCENARIOS))))

        print("\n\nMulti-Turn Scenarios:")
        print("-" * 50)
        for scenario_id, info in MULTI_TURN_SCENARIOS.items():
            print(f"  {scenario_id}")
            print(f"    {info['name']}: {info['description']}")
        return

    # Check server health
    print("Checking server health...")
    if not check_server_health():
        print("\nError: Server is not running or not healthy.")
        print("Start the server first:")
        print("  cd agents/research-assistant")
        print("  uv run python -m research_assistant")
        sys.exit(1)
    print("Server is healthy.\n")

    results = []
    verbose = not args.quiet

    # Run specific scenario (single-turn or multi-turn)
    if args.scenario:
        # First check single-turn scenarios
        scenario = next((s for s in SCENARIOS if s.name == args.scenario), None)
        if scenario:
            results.append(run_scenario(scenario, verbose=verbose))
        # Then check multi-turn scenarios
        elif args.scenario in MULTI_TURN_SCENARIOS:
            runner = MULTI_TURN_SCENARIOS[args.scenario]["runner"]
            results.extend(runner(verbose=verbose))
        else:
            print(f"Error: Scenario '{args.scenario}' not found.")
            print("Use --list to see available scenarios.")
            sys.exit(1)

    # Run category
    elif args.category:
        category_scenarios = [s for s in SCENARIOS if s.category == args.category]
        if not category_scenarios:
            print(f"Error: Category '{args.category}' not found.")
            print("Available categories:", ", ".join(sorted(set(s.category for s in SCENARIOS))))
            sys.exit(1)
        for scenario in category_scenarios:
            results.append(run_scenario(scenario, verbose=verbose))

    # Run multi-turn scenarios
    elif args.multi_turn:
        if args.multi_turn == "all":
            results.extend(run_all_multi_turn_scenarios(verbose=verbose))
        elif args.multi_turn in MULTI_TURN_SCENARIOS:
            runner = MULTI_TURN_SCENARIOS[args.multi_turn]["runner"]
            results.extend(runner(verbose=verbose))
        else:
            print(f"Error: Multi-turn scenario '{args.multi_turn}' not found.")
            print("Available multi-turn scenarios:")
            for scenario_id in MULTI_TURN_SCENARIOS:
                print(f"  - {scenario_id}")
            sys.exit(1)

    # Run all
    elif args.all:
        print("Running all single-turn scenarios...")
        for scenario in SCENARIOS:
            results.append(run_scenario(scenario, verbose=verbose))
        print("\nRunning all multi-turn scenarios...")
        results.extend(run_all_multi_turn_scenarios(verbose=verbose))

    # Default: show help
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  # Single-turn scenarios")
        print("  python examples/test_scenarios.py --scenario safety_assessment")
        print("  python examples/test_scenarios.py --category competitive")
        print("")
        print("  # Multi-turn scenarios")
        print("  python examples/test_scenarios.py --multi-turn                    # Run all")
        print("  python examples/test_scenarios.py --multi-turn btk_analysis       # Run specific")
        print("  python examples/test_scenarios.py --multi-turn competitive_deep_dive")
        print("  python examples/test_scenarios.py --multi-turn target_validation")
        print("  python examples/test_scenarios.py --multi-turn compound_optimization")
        print("  python examples/test_scenarios.py --multi-turn safety_investigation")
        print("  python examples/test_scenarios.py --multi-turn analysis_pivot")
        print("")
        print("  # All scenarios")
        print("  python examples/test_scenarios.py --all")
        return

    # Print summary
    if results:
        print_summary(results)

        # Save results to JSON
        output_file = "test_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
