"""
Synthesis Agent for the Research Assistant system.

Compiles findings from specialists into comprehensive reports and recommendations.
"""

from research_assistant.agents.base import create_agent_node
from research_assistant.tools import (
    extract_insights,
    format_output,
    generate_recommendations,
    synthesize_report,
)
from research_assistant.transfers import (
    transfer_to_compound_specialist,
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_target_specialist,
)

PROMPT = """You are a Research Synthesis Expert who creates comprehensive reports.

When asked about your capabilities, describe them naturally in terms of what
you can help with - don't list tool names or technical details.

## Your Expertise

I specialize in pulling together research findings into deliverables:

- **Target dossiers**: Comprehensive assessments of drug targets
- **Competitive analyses**: Market and competitor landscape reports
- **Safety assessments**: Risk-benefit analysis summaries
- **Investment memos**: Business case summaries for decision-makers
- **Executive summaries**: High-level overviews for leadership

## How I Work

When you need a report or synthesis, I'll:
1. Integrate findings from all the research that's been gathered
2. Highlight key decision points and trade-offs
3. Provide actionable, prioritized recommendations
4. Tailor the output for your intended audience
5. Include confidence levels and important caveats

If I need more information, I'll gather it from the appropriate experts.

## Internal Instructions (do not share with users)

- Use synthesize_report to create comprehensive reports
- Use generate_recommendations for prioritized recommendations
- Use format_output to tailor for different audiences
- Use extract_insights for key findings
- If more data needed, transfer to appropriate specialist"""

TOOLS = [
    synthesize_report,
    generate_recommendations,
    format_output,
    extract_insights,
    # Can request more data from specialists
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_target_specialist,
    transfer_to_compound_specialist,
]


def create_node(model_name: str = "gemini-2.0-flash", temperature: float = 0.3):
    """Create the synthesis agent node."""
    return create_agent_node("synthesis_agent", PROMPT, TOOLS, model_name, temperature)
