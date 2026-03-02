"""
Composable tools for Research Assistant agent.

Tools are organized into three layers for composability:
1. RETRIEVAL - Get raw data from various sources
2. ANALYSIS - Process, compare, score, and analyze data
3. SYNTHESIS - Combine insights and generate outputs

Each tool returns structured data that can be consumed by downstream tools.

All tools are decorated with @observe.tool() for tracing in Rhesis.
"""

from typing import Any

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from rhesis.sdk import observe  # Used for @observe.llm() on simulate_tool_response

# LLM for simulating tool responses
_tool_llm = None


def get_tool_llm() -> ChatGoogleGenerativeAI:
    """Get or create the LLM for tool simulation."""
    global _tool_llm
    if _tool_llm is None:
        _tool_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
    return _tool_llm


@observe.llm(provider="google", model="gemini-2.0-flash")
def simulate_tool_response(tool_name: str, prompt: str, output_format: str = "") -> str:
    """Simulate a tool response using LLM."""
    llm = get_tool_llm()
    format_instruction = f"\n\nOutput Format:\n{output_format}" if output_format else ""
    system_prompt = f"""You are simulating a scientific data tool called '{tool_name}'.
Generate realistic, scientifically plausible mock data.
Be concise but informative. Include specific data points, numbers, and references.
Return structured data that can be processed by downstream tools.{format_instruction}"""

    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    )
    return response.content


# =============================================================================
# LAYER 1: RETRIEVAL TOOLS - Get raw data from sources
# =============================================================================


@tool
def retrieve_safety_data(
    entity_name: str,
    entity_type: str = "target",
    data_sources: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieve safety and toxicity data for a target, compound, or pathway.

    Use this tool to get raw safety data that can then be analyzed or combined
    with other data sources.

    Args:
        entity_name: Name of the entity (target, compound, pathway)
        entity_type: Type of entity (target, compound, pathway, drug_class)
        data_sources: Specific sources to query (fda, ema, literature, clinical_trials)

    Returns:
        Structured safety data including toxicities, adverse events, and warnings
    """
    sources = data_sources or ["fda", "ema", "literature", "clinical_trials"]
    prompt = f"""Retrieve safety data for {entity_type}: {entity_name}
Data sources: {", ".join(sources)}

Return structured data including:
- on_target_toxicities: list of {{name, severity (1-5), frequency, mechanism}}
- off_target_effects: list of {{name, severity, affected_organ}}
- clinical_adverse_events: list of {{event, incidence_rate, grade}}
- regulatory_warnings: list of {{agency, warning_type, description}}
- overall_risk_score: 1-10 with rationale"""

    result = simulate_tool_response("SafetyDatabase", prompt)
    return {
        "tool": "retrieve_safety_data",
        "entity_name": entity_name,
        "entity_type": entity_type,
        "data_sources": sources,
        "data": result,
        "data_type": "safety_profile",
    }


@tool
def retrieve_literature(
    query: str,
    source_types: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Search and retrieve scientific literature from multiple databases.

    Use this to gather publications, reviews, and reports that can be
    analyzed or synthesized with other data.

    Args:
        query: Search query (supports boolean operators)
        source_types: Sources to search (pubmed, patents, preprints, internal_reports)
        filters: Optional filters (year_from, year_to, article_type, organism)
        max_results: Maximum results to return

    Returns:
        List of literature items with metadata and key findings
    """
    sources = source_types or ["pubmed", "patents", "internal_reports"]
    filters = filters or {}
    prompt = f"""Search literature for: "{query}"
Sources: {", ".join(sources)}
Filters: {filters}
Max results: {max_results}

Return structured data:
- total_hits: number
- results: list of {{
    id, title, authors, source, year, 
    abstract_summary, key_findings (list),
    relevance_score (1-10), citation_count
  }}
- search_metadata: {{query_terms, filters_applied}}"""

    result = simulate_tool_response("LiteratureSearch", prompt)
    return {
        "tool": "retrieve_literature",
        "query": query,
        "sources": sources,
        "filters": filters,
        "data": result,
        "data_type": "literature_results",
    }


@tool
def retrieve_target_info(
    target_name: str,
    info_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieve biological and functional information about a molecular target.

    Gets foundational target data that can be used for druggability analysis,
    safety assessment, or target prioritization.

    Args:
        target_name: Gene symbol, protein name, or pathway
        info_types: Types of info (biology, genetics, expression, pathways, disease_links)

    Returns:
        Comprehensive target information organized by category
    """
    info_types = info_types or ["biology", "genetics", "expression", "pathways", "disease_links"]
    prompt = f"""Retrieve target information for: {target_name}
Information categories: {", ".join(info_types)}

Return structured data:
- target_id: official symbol/ID
- aliases: list of alternative names
- target_class: (kinase, GPCR, ion_channel, etc.)
- biology: {{function, localization, protein_interactions}}
- genetics: {{chromosome, variants, disease_associations}}
- expression: {{tissues (list with levels), disease_vs_normal}}
- pathways: list of {{pathway_name, role, downstream_effects}}
- disease_links: list of {{disease, evidence_level, mechanism}}
- validation_level: (genetic, pharmacological, clinical)"""

    result = simulate_tool_response("TargetDatabase", prompt)
    return {
        "tool": "retrieve_target_info",
        "target_name": target_name,
        "info_types": info_types,
        "data": result,
        "data_type": "target_profile",
    }


@tool
def retrieve_compound_data(
    compound_identifier: str,
    data_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieve chemical and pharmacological data for a compound.

    Gets compound properties, activity data, and ADMET information for
    synthesis planning, optimization, or comparison.

    Args:
        compound_identifier: SMILES, compound name, or internal ID
        data_types: Types of data (structure, activity, admet, synthesis, clinical)

    Returns:
        Comprehensive compound data organized by category
    """
    data_types = data_types or ["structure", "activity", "admet", "synthesis"]
    prompt = f"""Retrieve compound data for: {compound_identifier}
Data categories: {", ".join(data_types)}

Return structured data:
- compound_id: identifier
- structure: {{smiles, molecular_weight, logP, tpsa, hbd, hba}}
- activity: list of {{target, assay_type, IC50/EC50, selectivity}}
- admet: {{absorption, distribution, metabolism, excretion, toxicity_flags}}
- synthesis: {{complexity_score, key_intermediates, estimated_steps}}
- clinical_status: if applicable"""

    result = simulate_tool_response("CompoundDatabase", prompt)
    return {
        "tool": "retrieve_compound_data",
        "compound_identifier": compound_identifier,
        "data_types": data_types,
        "data": result,
        "data_type": "compound_profile",
    }


@tool
def retrieve_market_data(
    category: str,
    region: str = "global",
    segments: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieve market and competitive intelligence data.

    Gets market size, competitors, and trends for competitive landscape
    analysis and strategic planning.

    Args:
        category: Therapeutic area, product category, or technology
        region: Geographic region (global, us, eu, asia, specific countries)
        segments: Market segments to include (approved, pipeline, generic, biosimilar)

    Returns:
        Market data with size, growth, competitors, and trends
    """
    segments = segments or ["approved", "pipeline"]
    prompt = f"""Retrieve market data for: {category}
Region: {region}
Segments: {", ".join(segments)}

Return structured data:
- market_size: {{current_value, currency, year}}
- growth: {{cagr, forecast_value, forecast_year}}
- competitors: list of {{company, market_share, key_products}}
- pipeline: list of {{company, product, phase, expected_launch}}
- trends: list of {{trend, impact, timeline}}
- unmet_needs: list of opportunities"""

    result = simulate_tool_response("MarketIntelligence", prompt)
    return {
        "tool": "retrieve_market_data",
        "category": category,
        "region": region,
        "segments": segments,
        "data": result,
        "data_type": "market_intelligence",
    }


@tool
def retrieve_patent_data(
    subject: str,
    search_scope: str = "claims",
    time_range_years: int = 10,
) -> dict[str, Any]:
    """
    Retrieve patent landscape data for a target, compound, or technology.

    Gets patent filings, freedom to operate analysis, and IP landscape
    for strategic decision-making.

    Args:
        subject: Target, compound, or technology to search
        search_scope: What to search (claims, full_text, title_abstract)
        time_range_years: How many years back to search

    Returns:
        Patent landscape with key patents, assignees, and FTO analysis
    """
    prompt = f"""Retrieve patent data for: {subject}
Search scope: {search_scope}
Time range: last {time_range_years} years

Return structured data:
- total_patents: count
- key_patents: list of {{
    patent_number, title, assignee, filing_date, 
    status, expiry_date, relevance_score
  }}
- assignee_landscape: list of {{company, patent_count, focus_areas}}
- fto_assessment: {{risk_level, blocking_patents, white_space}}
- trends: {{filing_trend, technology_evolution}}"""

    result = simulate_tool_response("PatentDatabase", prompt)
    return {
        "tool": "retrieve_patent_data",
        "subject": subject,
        "search_scope": search_scope,
        "time_range_years": time_range_years,
        "data": result,
        "data_type": "patent_landscape",
    }


@tool
def retrieve_experimental_data(
    entity_name: str,
    experiment_types: list[str] | None = None,
    data_source: str = "internal",
) -> dict[str, Any]:
    """
    Retrieve experimental/assay data from internal or external databases.

    Gets raw experimental results that can be analyzed for validation,
    optimization, or decision-making.

    Args:
        entity_name: Target or compound to query
        experiment_types: Types (binding, functional, cell, animal, clinical)
        data_source: Source (internal, chembl, pubchem, clinical_trials)

    Returns:
        Experimental data with assay results and metadata
    """
    experiment_types = experiment_types or ["binding", "functional", "cell"]
    prompt = f"""Retrieve experimental data for: {entity_name}
Experiment types: {", ".join(experiment_types)}
Data source: {data_source}

Return structured data:
- experiments: list of {{
    experiment_id, type, assay_name, 
    result_value, result_unit, conditions,
    n_replicates, std_dev, quality_score
  }}
- summary_statistics: {{mean, median, range, n_experiments}}
- data_quality: overall assessment"""

    result = simulate_tool_response("ExperimentalDatabase", prompt)
    return {
        "tool": "retrieve_experimental_data",
        "entity_name": entity_name,
        "experiment_types": experiment_types,
        "data_source": data_source,
        "data": result,
        "data_type": "experimental_results",
    }


# =============================================================================
# LAYER 2: ANALYSIS TOOLS - Process and analyze data
# =============================================================================


@tool
def analyze_and_score(
    input_data: str,
    analysis_type: str,
    scoring_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """
    Analyze input data and compute scores based on specified criteria.

    Use this to process retrieved data and generate quantitative assessments.
    Can be chained after retrieval tools or other analysis tools.

    Args:
        input_data: Data to analyze (from previous tool or description)
        analysis_type: Type of analysis (druggability, safety_risk, feasibility, novelty)
        scoring_criteria: Specific criteria to score (depends on analysis_type)

    Returns:
        Analysis results with scores and supporting evidence
    """
    criteria = scoring_criteria or ["overall"]
    prompt = f"""Analyze the following data and compute {analysis_type} scores.
Scoring criteria: {", ".join(criteria)}

Input data:
{input_data}

Return structured analysis:
- analysis_type: {analysis_type}
- overall_score: 0-100 with confidence interval
- criteria_scores: dict of {{criterion: {{score, evidence, confidence}}}}
- key_factors: list of factors influencing scores
- limitations: any caveats or data gaps
- recommendations: based on analysis"""

    result = simulate_tool_response("AnalysisEngine", prompt)
    return {
        "tool": "analyze_and_score",
        "analysis_type": analysis_type,
        "scoring_criteria": criteria,
        "data": result,
        "data_type": "scored_analysis",
    }


@tool
def compare_entities(
    entities: list[str],
    comparison_dimensions: list[str],
    input_data: str = "",
) -> dict[str, Any]:
    """
    Compare multiple entities across specified dimensions.

    Use this to evaluate alternatives, benchmark options, or identify
    differentiating factors. Can use data from previous retrieval tools.

    Args:
        entities: List of entity names to compare
        comparison_dimensions: Dimensions to compare (efficacy, safety, cost, novelty, etc.)
        input_data: Optional data from previous tools to inform comparison

    Returns:
        Comparison matrix with scores and differentiating factors
    """
    prompt = f"""Compare the following entities: {", ".join(entities)}
Comparison dimensions: {", ".join(comparison_dimensions)}

{("Additional context: " + input_data) if input_data else ""}

Return structured comparison:
- comparison_matrix: {{
    entity: {{dimension: {{score, rationale}}}}
  }} for each entity
- rankings_by_dimension: {{dimension: [ranked entities]}}
- overall_ranking: with methodology
- key_differentiators: what sets each apart
- trade_offs: important trade-offs to consider"""

    result = simulate_tool_response("ComparisonEngine", prompt)
    return {
        "tool": "compare_entities",
        "entities": entities,
        "comparison_dimensions": comparison_dimensions,
        "data": result,
        "data_type": "comparison_analysis",
    }


@tool
def identify_gaps(
    subject: str,
    input_data: str,
    gap_categories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Identify knowledge gaps and data deficiencies in the provided information.

    Use after retrieval tools to find missing information and suggest
    experiments or analyses to fill gaps.

    Args:
        subject: What the analysis is about
        input_data: Data to analyze for gaps (from previous tools)
        gap_categories: Categories to check (biology, safety, efficacy, translation, IP)

    Returns:
        List of gaps with impact assessment and suggested actions
    """
    categories = gap_categories or ["biology", "safety", "efficacy", "translation"]
    prompt = f"""Identify knowledge gaps for: {subject}
Categories to analyze: {", ".join(categories)}

Input data to analyze:
{input_data}

Return structured gap analysis:
- gaps: list of {{
    gap_id, category, description, 
    impact (high/medium/low), 
    current_evidence_level,
    suggested_experiments: list of {{experiment, timeline, resources}},
    priority_score
  }}
- critical_gaps: subset that are blocking
- gap_summary: by category
- recommended_next_steps: prioritized list"""

    result = simulate_tool_response("GapAnalyzer", prompt)
    return {
        "tool": "identify_gaps",
        "subject": subject,
        "gap_categories": categories,
        "data": result,
        "data_type": "gap_analysis",
    }


@tool
def filter_and_rank(
    items: list[str],
    ranking_criteria: list[str],
    filter_conditions: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
    input_data: str = "",
) -> dict[str, Any]:
    """
    Filter items based on conditions and rank by weighted criteria.

    Use this to prioritize targets, compounds, or options based on
    multiple criteria with customizable weights.

    Args:
        items: List of items to filter and rank
        ranking_criteria: Criteria for ranking (e.g., druggability, safety, novelty)
        filter_conditions: Conditions to filter by (e.g., {"safety_score": ">50"})
        weights: Weights for each criterion (default: equal weights)
        input_data: Optional data from previous tools

    Returns:
        Filtered and ranked list with scores and rationale
    """
    filter_conditions = filter_conditions or {}
    weights = weights or {c: 1.0 for c in ranking_criteria}
    prompt = f"""Filter and rank the following items: {", ".join(items)}
Ranking criteria: {", ".join(ranking_criteria)}
Weights: {weights}
Filter conditions: {filter_conditions}

{("Additional data: " + input_data) if input_data else ""}

Return structured results:
- filtered_items: items that passed filters
- excluded_items: items excluded and why
- ranked_list: list of {{
    rank, item, 
    overall_score,
    criteria_scores: {{criterion: score}},
    rationale
  }}
- methodology: how scores were calculated
- sensitivity: how rankings change with different weights"""

    result = simulate_tool_response("FilterRankEngine", prompt)
    return {
        "tool": "filter_and_rank",
        "items": items,
        "ranking_criteria": ranking_criteria,
        "weights": weights,
        "data": result,
        "data_type": "ranked_list",
    }


@tool
def compute_routes(
    target_outcome: str,
    constraints: dict[str, Any] | None = None,
    optimization_goal: str = "balanced",
    input_data: str = "",
) -> dict[str, Any]:
    """
    Compute optimal routes or pathways to achieve a target outcome.

    Use for synthesis route planning, development pathways, or
    strategic planning. Can incorporate data from previous tools.

    Args:
        target_outcome: What to achieve (compound synthesis, target validation, etc.)
        constraints: Constraints to respect (cost, time, resources, IP)
        optimization_goal: What to optimize (cost, speed, yield, green_chemistry, balanced)
        input_data: Optional context from previous tools

    Returns:
        Ranked routes with steps, costs, and feasibility assessment
    """
    constraints = constraints or {}
    prompt = f"""Compute optimal routes for: {target_outcome}
Optimization goal: {optimization_goal}
Constraints: {constraints}

{("Context: " + input_data) if input_data else ""}

Return structured routes:
- routes: list of {{
    route_id, name, description,
    steps: list of {{step_number, action, requirements, duration}},
    total_cost_estimate,
    total_time_estimate,
    feasibility_score,
    risks: list,
    optimization_score
  }}
- recommended_route: with rationale
- alternatives_analysis: trade-offs between routes"""

    result = simulate_tool_response("RouteOptimizer", prompt)
    return {
        "tool": "compute_routes",
        "target_outcome": target_outcome,
        "optimization_goal": optimization_goal,
        "constraints": constraints,
        "data": result,
        "data_type": "route_analysis",
    }


@tool
def extract_insights(
    input_data: str,
    focus_areas: list[str] | None = None,
    insight_type: str = "actionable",
) -> dict[str, Any]:
    """
    Extract key insights from provided data.

    Use after retrieval or analysis tools to distill findings into
    actionable insights that can inform decisions or reports.

    Args:
        input_data: Data to extract insights from
        focus_areas: Specific areas to focus on
        insight_type: Type of insights (actionable, strategic, technical, risk)

    Returns:
        Structured insights with evidence and confidence levels
    """
    focus_areas = focus_areas or ["key_findings", "opportunities", "risks"]
    prompt = f"""Extract {insight_type} insights from the following data.
Focus areas: {", ".join(focus_areas)}

Data:
{input_data}

Return structured insights:
- insights: list of {{
    insight_id, category, statement,
    supporting_evidence: list,
    confidence_level (high/medium/low),
    actionability_score,
    implications
  }}
- top_insights: most important findings
- contradictions: any conflicting information
- confidence_summary: overall data quality"""

    result = simulate_tool_response("InsightExtractor", prompt)
    return {
        "tool": "extract_insights",
        "focus_areas": focus_areas,
        "insight_type": insight_type,
        "data": result,
        "data_type": "extracted_insights",
    }


# =============================================================================
# LAYER 3: SYNTHESIS TOOLS - Combine and output
# =============================================================================


@tool
def synthesize_report(
    report_type: str,
    input_data: str,
    sections: list[str] | None = None,
    audience: str = "scientific",
) -> dict[str, Any]:
    """
    Synthesize a comprehensive report from multiple data inputs.

    Use this to combine outputs from retrieval and analysis tools into
    a structured report format.

    Args:
        report_type: Type of report (target_dossier, competitive_analysis, safety_assessment)
        input_data: Combined data from previous tools
        sections: Sections to include in report
        audience: Target audience (scientific, executive, regulatory)

    Returns:
        Structured report with executive summary and detailed sections
    """
    default_sections = {
        "target_dossier": [
            "executive_summary",
            "biology",
            "validation",
            "safety",
            "druggability",
            "competition",
            "ip",
            "recommendations",
        ],
        "competitive_analysis": [
            "executive_summary",
            "market_overview",
            "competitor_profiles",
            "pipeline",
            "trends",
            "opportunities",
        ],
        "safety_assessment": [
            "executive_summary",
            "safety_profile",
            "risk_analysis",
            "mitigation",
            "monitoring",
            "conclusions",
        ],
    }
    sections = sections or default_sections.get(
        report_type, ["executive_summary", "analysis", "conclusions"]
    )

    prompt = f"""Synthesize a {report_type} report for {audience} audience.
Sections: {", ".join(sections)}

Input data:
{input_data}

Return structured report:
- title: report title
- executive_summary: 3-5 key points
- sections: dict of {{
    section_name: {{
      content: detailed content,
      key_points: list,
      data_quality: assessment
    }}
  }}
- conclusions: main conclusions
- recommendations: actionable next steps
- appendices: supporting data references"""

    result = simulate_tool_response("ReportSynthesizer", prompt)
    return {
        "tool": "synthesize_report",
        "report_type": report_type,
        "sections": sections,
        "audience": audience,
        "data": result,
        "data_type": "synthesized_report",
    }


@tool
def generate_recommendations(
    context: str,
    input_data: str,
    recommendation_type: str = "strategic",
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate actionable recommendations based on analysis.

    Use at the end of an analysis chain to produce concrete
    recommendations for decision-making.

    Args:
        context: What the recommendations are for
        input_data: Data from previous tools to base recommendations on
        recommendation_type: Type (strategic, tactical, experimental, go_no_go)
        constraints: Constraints to consider (budget, timeline, resources)

    Returns:
        Prioritized recommendations with rationale and implementation guidance
    """
    constraints = constraints or {}
    prompt = f"""Generate {recommendation_type} recommendations for: {context}
Constraints: {constraints}

Based on:
{input_data}

Return structured recommendations:
- recommendations: list of {{
    priority (1-5), 
    recommendation,
    rationale,
    expected_impact,
    resources_required,
    timeline,
    risks,
    success_metrics
  }}
- decision_summary: key decision points
- alternative_paths: if primary recommendations aren't feasible
- immediate_actions: what to do first"""

    result = simulate_tool_response("RecommendationEngine", prompt)
    return {
        "tool": "generate_recommendations",
        "context": context,
        "recommendation_type": recommendation_type,
        "constraints": constraints,
        "data": result,
        "data_type": "recommendations",
    }


@tool
def format_output(
    input_data: str,
    output_format: str,
    include_sections: list[str] | None = None,
) -> dict[str, Any]:
    """
    Format analysis results for specific output needs.

    Use to prepare data for presentation, export, or further processing.

    Args:
        input_data: Data to format
        output_format: Desired format (summary, detailed, table, bullet_points, narrative)
        include_sections: Specific sections to include

    Returns:
        Formatted output ready for presentation or export
    """
    include_sections = include_sections or ["all"]
    prompt = f"""Format the following data as {output_format}.
Include sections: {", ".join(include_sections)}

Data:
{input_data}

Return formatted output appropriate for the requested format."""

    result = simulate_tool_response("OutputFormatter", prompt)
    return {
        "tool": "format_output",
        "output_format": output_format,
        "include_sections": include_sections,
        "data": result,
        "data_type": "formatted_output",
    }


# =============================================================================
# UTILITY TOOLS - Support composability
# =============================================================================


@tool
def update_context(
    current_context: str,
    modifications: dict[str, Any],
    action: str = "refine",
) -> dict[str, Any]:
    """
    Update or refine the analysis context based on new information or user feedback.

    Use this to modify parameters, exclude data, or pivot the analysis
    based on intermediate results or user input.

    Args:
        current_context: Current state of the analysis
        modifications: Changes to apply (exclude, include, reweight, focus)
        action: Type of update (refine, pivot, exclude, expand)

    Returns:
        Updated context ready for further analysis
    """
    prompt = f"""Update analysis context.
Action: {action}
Modifications: {modifications}

Current context:
{current_context}

Return:
- updated_context: modified context
- changes_applied: list of changes made
- impact_assessment: how this affects the analysis
- next_suggested_steps: what to do next"""

    result = simulate_tool_response("ContextManager", prompt)
    return {
        "tool": "update_context",
        "action": action,
        "modifications": modifications,
        "data": result,
        "data_type": "updated_context",
    }


@tool
def request_clarification(
    question: str,
    options: list[str] | None = None,
    context: str = "",
) -> dict[str, Any]:
    """
    Request clarification or input from the user to continue analysis.

    Use when the analysis needs human guidance, validation, or
    decision-making at a critical point.

    Args:
        question: The question to ask the user
        options: Predefined options if applicable
        context: Context to help user understand the question

    Returns:
        Structured request for user input
    """
    return {
        "tool": "request_clarification",
        "question": question,
        "options": options,
        "context": context,
        "data": f"Clarification needed: {question}",
        "data_type": "user_input_request",
        "requires_response": True,
    }


@tool
def save_checkpoint(
    checkpoint_name: str,
    data_to_save: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a checkpoint of current analysis state for later reference.

    Use to save intermediate results, enable pivoting, or create
    reference points for comparison.

    Args:
        checkpoint_name: Name for this checkpoint
        data_to_save: Data to checkpoint
        tags: Tags for categorization and retrieval

    Returns:
        Confirmation with checkpoint ID and retrieval info
    """
    import uuid

    checkpoint_id = str(uuid.uuid4())[:8]
    return {
        "tool": "save_checkpoint",
        "checkpoint_id": checkpoint_id,
        "checkpoint_name": checkpoint_name,
        "tags": tags or [],
        "data": f"Checkpoint '{checkpoint_name}' saved with ID: {checkpoint_id}",
        "data_type": "checkpoint_confirmation",
    }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Layer 1: Retrieval
RETRIEVAL_TOOLS = [
    retrieve_safety_data,
    retrieve_literature,
    retrieve_target_info,
    retrieve_compound_data,
    retrieve_market_data,
    retrieve_patent_data,
    retrieve_experimental_data,
]

# Layer 2: Analysis
ANALYSIS_TOOLS = [
    analyze_and_score,
    compare_entities,
    identify_gaps,
    filter_and_rank,
    compute_routes,
    extract_insights,
]

# Layer 3: Synthesis
SYNTHESIS_TOOLS = [
    synthesize_report,
    generate_recommendations,
    format_output,
]

# Utility
UTILITY_TOOLS = [
    update_context,
    request_clarification,
    save_checkpoint,
]

ALL_TOOLS = RETRIEVAL_TOOLS + ANALYSIS_TOOLS + SYNTHESIS_TOOLS + UTILITY_TOOLS


def get_tool_descriptions() -> str:
    """Get formatted descriptions of all available tools by layer."""
    lines = ["## Available Tools\n"]

    layers = [
        ("Retrieval (Get Data)", RETRIEVAL_TOOLS),
        ("Analysis (Process Data)", ANALYSIS_TOOLS),
        ("Synthesis (Generate Output)", SYNTHESIS_TOOLS),
        ("Utility (Support)", UTILITY_TOOLS),
    ]

    for layer_name, tools in layers:
        lines.append(f"### {layer_name}")
        for t in tools:
            desc = t.description.split("\n")[0] if t.description else ""
            lines.append(f"- **{t.name}**: {desc}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# SPECIALIST TOOL GROUPS (for multi-agent system)
# =============================================================================

# Tools for Safety Specialist
SAFETY_DOMAIN_TOOLS = [
    retrieve_safety_data,
    retrieve_experimental_data,
    analyze_and_score,
    identify_gaps,
    extract_insights,
]

# Tools for Target Specialist
TARGET_DOMAIN_TOOLS = [
    retrieve_target_info,
    retrieve_experimental_data,
    analyze_and_score,
    compare_entities,
    identify_gaps,
    filter_and_rank,
    extract_insights,
]

# Tools for Compound Specialist
COMPOUND_DOMAIN_TOOLS = [
    retrieve_compound_data,
    retrieve_experimental_data,
    analyze_and_score,
    compare_entities,
    compute_routes,
    filter_and_rank,
    extract_insights,
]

# Tools for Literature Specialist
LITERATURE_DOMAIN_TOOLS = [
    retrieve_literature,
    retrieve_patent_data,
    extract_insights,
    identify_gaps,
]

# Tools for Market Specialist
MARKET_DOMAIN_TOOLS = [
    retrieve_market_data,
    retrieve_patent_data,
    analyze_and_score,
    compare_entities,
    extract_insights,
]

# Tools for Synthesis Agent
SYNTHESIS_DOMAIN_TOOLS = [
    synthesize_report,
    generate_recommendations,
    format_output,
    extract_insights,
]
