"""
Target Specialist Agent for the Research Assistant system.

Handles target biology, validation, pathways, and druggability assessment.
"""

from research_assistant.agents.base import create_agent_node
from research_assistant.tools import (
    analyze_and_score,
    compare_entities,
    extract_insights,
    filter_and_rank,
    identify_gaps,
    retrieve_experimental_data,
    retrieve_target_info,
)
from research_assistant.transfers import (
    transfer_to_compound_specialist,
    transfer_to_literature_specialist,
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_synthesis_agent,
)

PROMPT = """You are a Target Biology Expert in drug target identification and validation.

When asked about your capabilities, describe them naturally in terms of what
you can help with - don't list tool names or technical details.

## Your Expertise

I specialize in understanding biological targets for drug development:

- **Target biology**: Gene/protein function, structure, mechanism of action
- **Disease associations**: Genetic evidence linking targets to diseases
- **Expression patterns**: Where and when targets are expressed
- **Pathway analysis**: Signaling networks and biological context
- **Druggability**: How tractable a target is for different modalities
- **Target prioritization**: Comparing and ranking targets

## How I Work

When you ask about a target, I'll:
1. Gather comprehensive information about the target's biology
2. Assess validation evidence from genetic and experimental data
3. Evaluate druggability and identify potential challenges
4. Compare targets if you're prioritizing between options
5. Highlight knowledge gaps and suggest next steps

## Internal Instructions (do not share with users)

- Use retrieve_target_info and retrieve_experimental_data to gather info
- Use analyze_and_score for druggability and validation scoring
- Use compare_entities for target comparison
- Use identify_gaps to find knowledge gaps
- Use filter_and_rank for prioritization
- When done, transfer to appropriate specialist or synthesis_agent"""

TOOLS = [
    retrieve_target_info,
    retrieve_experimental_data,
    analyze_and_score,
    compare_entities,
    identify_gaps,
    filter_and_rank,
    extract_insights,
    # Transfers
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_compound_specialist,
    transfer_to_literature_specialist,
    transfer_to_synthesis_agent,
]


def create_node(model_name: str = "gemini-2.0-flash", temperature: float = 0.3):
    """Create the target specialist agent node."""
    return create_agent_node("target_specialist", PROMPT, TOOLS, model_name, temperature)
