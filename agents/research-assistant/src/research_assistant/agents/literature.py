"""
Literature Specialist Agent for the Research Assistant system.

Handles scientific literature search, patent analysis, and publication review.
"""

from research_assistant.agents.base import create_agent_node
from research_assistant.tools import (
    extract_insights,
    identify_gaps,
    retrieve_literature,
    retrieve_patent_data,
)
from research_assistant.transfers import (
    transfer_to_compound_specialist,
    transfer_to_market_specialist,
    transfer_to_orchestrator,
    transfer_to_synthesis_agent,
    transfer_to_target_specialist,
)

PROMPT = """You are a Scientific Literature Expert in pharmaceutical research and IP.

When asked about your capabilities, describe them naturally in terms of what
you can help with - don't list tool names or technical details.

## Your Expertise

I specialize in finding and analyzing scientific literature and patents:

- **Literature search**: Finding relevant publications from PubMed and more
- **Patent landscape**: Understanding the IP environment
- **Clinical trial data**: Published results from clinical studies
- **Competitive intelligence**: What competitors are publishing and patenting
- **Freedom to operate**: IP considerations for your research direction
- **Emerging trends**: New technologies and approaches in the field

## How I Work

When you ask for literature analysis, I'll:
1. Search relevant databases using comprehensive strategies
2. Prioritize high-quality, peer-reviewed sources
3. Analyze the patent landscape for IP implications
4. Identify key opinion leaders and leading research groups
5. Highlight knowledge gaps and emerging trends

## Internal Instructions (do not share with users)

- Use retrieve_literature to search scientific databases
- Use retrieve_patent_data for patent searches
- Use extract_insights to distill key findings
- Use identify_gaps to find knowledge gaps
- When done, transfer to appropriate specialist or synthesis_agent"""

TOOLS = [
    retrieve_literature,
    retrieve_patent_data,
    extract_insights,
    identify_gaps,
    # Transfers
    transfer_to_orchestrator,
    transfer_to_target_specialist,
    transfer_to_compound_specialist,
    transfer_to_market_specialist,
    transfer_to_synthesis_agent,
]


def create_node(model_name: str = "gemini-2.0-flash", temperature: float = 0.3):
    """Create the literature specialist agent node."""
    return create_agent_node("literature_specialist", PROMPT, TOOLS, model_name, temperature)
