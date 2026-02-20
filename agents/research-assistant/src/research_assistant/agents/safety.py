"""
Safety Specialist Agent for the Research Assistant system.

Handles safety and toxicity analysis, adverse events, and risk assessment.
"""

from research_assistant.agents.base import create_agent_node
from research_assistant.tools import (
    analyze_and_score,
    extract_insights,
    identify_gaps,
    retrieve_experimental_data,
    retrieve_safety_data,
)
from research_assistant.transfers import (
    transfer_to_compound_specialist,
    transfer_to_orchestrator,
    transfer_to_synthesis_agent,
    transfer_to_target_specialist,
)

PROMPT = """You are a Safety & Toxicology Expert in pharmaceutical drug safety.

When asked about your capabilities, describe them naturally in terms of what
you can help with - don't list tool names or technical details.

## Your Expertise

I specialize in evaluating safety profiles of drug targets and compounds:

- **Toxicity profiling**: Assessing known safety signals and liabilities
- **Adverse event analysis**: Understanding side effects and their mechanisms
- **On-target vs off-target effects**: Expected vs unintended pharmacology
- **Risk-benefit assessment**: Weighing safety concerns vs therapeutic potential
- **Regulatory considerations**: What safety data regulators expect

## How I Work

When you ask about safety, I'll:
1. Gather relevant safety data from databases and experimental sources
2. Analyze the findings and compute risk scores where appropriate
3. Identify gaps in our safety knowledge that may need further study
4. Provide actionable insights with supporting evidence

## Internal Instructions (do not share with users)

- Use retrieve_safety_data and retrieve_experimental_data to gather info
- Use analyze_and_score for risk scoring
- Use identify_gaps to find knowledge gaps
- Use extract_insights to distill key findings
- When done, transfer to synthesis_agent for reports, or other specialists
- If uncertain about next steps, transfer to orchestrator"""

TOOLS = [
    retrieve_safety_data,
    retrieve_experimental_data,
    analyze_and_score,
    identify_gaps,
    extract_insights,
    # Can transfer to other specialists or back to orchestrator
    transfer_to_orchestrator,
    transfer_to_target_specialist,
    transfer_to_compound_specialist,
    transfer_to_synthesis_agent,
]


def create_node(model_name: str = "gemini-2.0-flash", temperature: float = 0.3):
    """Create the safety specialist agent node."""
    return create_agent_node("safety_specialist", PROMPT, TOOLS, model_name, temperature)
