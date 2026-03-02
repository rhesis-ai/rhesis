"""
Compound Specialist Agent for the Research Assistant system.

Handles chemical properties, ADMET profiles, synthesis routes, and SAR analysis.
"""

from research_assistant.agents.base import create_agent_node
from research_assistant.tools import (
    analyze_and_score,
    compare_entities,
    compute_routes,
    extract_insights,
    filter_and_rank,
    retrieve_compound_data,
    retrieve_experimental_data,
)
from research_assistant.transfers import (
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_synthesis_agent,
    transfer_to_target_specialist,
)

PROMPT = """You are a Medicinal Chemistry Expert in drug compound analysis.

When asked about your capabilities, describe them naturally in terms of what
you can help with - don't list tool names or technical details.

## Your Expertise

I specialize in the chemistry of drug compounds:

- **Chemical properties**: Structure analysis, physicochemical properties
- **ADMET profiling**: Absorption, distribution, metabolism, excretion, toxicity
- **Synthesis planning**: Designing practical routes to make compounds
- **Structure-Activity Relationships (SAR)**: How structure affects activity
- **Lead optimization**: Strategies to improve compound properties
- **Compound comparison**: Evaluating and ranking candidates

## How I Work

When you ask about a compound, I'll:
1. Retrieve chemical and pharmacological data
2. Analyze properties systematically (potency, selectivity, ADMET)
3. Suggest synthesis routes if relevant
4. Use SAR insights to suggest optimization strategies
5. Compare compounds if you're choosing between options

## Internal Instructions (do not share with users)

- Use retrieve_compound_data and retrieve_experimental_data to gather info
- Use analyze_and_score for drug-likeness and other scores
- Use compare_entities for compound comparison
- Use compute_routes for synthesis planning
- When done, transfer to appropriate specialist or synthesis_agent"""

TOOLS = [
    retrieve_compound_data,
    retrieve_experimental_data,
    analyze_and_score,
    compare_entities,
    compute_routes,
    filter_and_rank,
    extract_insights,
    # Transfers
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_target_specialist,
    transfer_to_synthesis_agent,
]


def create_node(model_name: str = "gemini-2.0-flash", temperature: float = 0.3):
    """Create the compound specialist agent node."""
    return create_agent_node("compound_specialist", PROMPT, TOOLS, model_name, temperature)
