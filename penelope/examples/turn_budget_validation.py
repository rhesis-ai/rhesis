"""
Turn budget validation example for Penelope.

Systematically tests combinations of:
- min_turns: None, low, medium, high, equal-to-max
- max_turns: None, low, medium, high, equal-to-min
- Instructions: no turn mention, numbered steps, explicit turn directives,
  ambiguous "turn" wording

Validates:
1. Turn budget constraints are respected
2. No spurious "turn count" criteria when instructions don't mention turns
3. Goal judge correctly evaluates based on goal substance

Usage:
    uv run python turn_budget_validation.py -e <endpoint-id>
    uv run python turn_budget_validation.py -e <id> --suite quick
    uv run python turn_budget_validation.py -e <id> --case B2
"""

from common_args import create_base_parser

from rhesis.penelope import EndpointTarget, PenelopeAgent

# ---------------------------------------------------------------------------
# Instruction templates (reusable across min/max combos)
# ---------------------------------------------------------------------------

# No turn mention at all — just prose
INSTR_PROSE = (
    "Pretend you are planning a vacation. Ask the travel agent for "
    "destination recommendations, then follow up with questions about "
    "logistics like flights, hotels, and local activities."
)

# Numbered steps — should NOT be treated as turn count
INSTR_NUMBERED = (
    "Test the travel agent's trip planning capabilities.\n\n"
    "Specific steps:\n"
    "1. Ask about popular destinations for a winter trip\n"
    "2. Ask about transportation options\n"
    "3. Ask about accommodation recommendations\n\n"
    "Evaluate accuracy, helpfulness, and context retention."
)

# Bullet points — should NOT be treated as turn count
INSTR_BULLETS = (
    "Evaluate the travel agent's knowledge across these areas:\n"
    "- Destination recommendations for families\n"
    "- Budget-friendly travel tips\n"
    "- Safety and health advice for travelers\n"
    "- Cultural etiquette for international travel"
)

# Explicit turn directive — SHOULD be treated as turn count
INSTR_EXPLICIT_TURNS = (
    "You MUST send at least {n} messages to the travel agent.\n\n"
    "Cover these topics across your messages:\n"
    "- Best destinations for the season\n"
    "- Visa and entry requirements\n"
    "- Budget planning tips\n\n"
    "All {n} messages are required."
)

# Explicit "exactly N" directive — SHOULD be treated as turn count
INSTR_EXACT_TURNS = (
    "Execute exactly {n} turns of conversation.\n\n"
    "Each turn should explore a different travel topic. "
    "Do not send fewer than {n} messages."
)

# Mentions "turns" but NOT as a count (tricky wording)
INSTR_TURNS_OF_PHRASE = (
    "Test whether the travel agent uses creative turns of phrase "
    "and engaging language when describing destinations. Ask about "
    "a tropical destination, then ask about a contrasting cold-weather "
    "destination and compare the descriptive quality."
)

# Mentions "take turns" (not a count)
INSTR_TAKE_TURNS = (
    "Have the travel agent take turns suggesting destinations "
    "while you provide preferences and constraints. Start by "
    "asking about Asia, then react to their suggestion with "
    "a budget constraint and see how they adapt."
)

# Simple single-question instruction
INSTR_SIMPLE = (
    "Ask the travel agent for a single destination recommendation "
    "for a solo traveler and evaluate whether the response is helpful."
)

# Long detailed instruction with no turn mention
INSTR_DETAILED = (
    "Conduct a thorough evaluation of the travel agent's ability to "
    "plan a multi-city European itinerary. Explore city selection and "
    "route planning, transportation between cities, accommodation "
    "options, local activities and dining, and budget considerations. "
    "Each message should explore a different aspect. Assess depth, "
    "accuracy, and whether the agent maintains context across the "
    "full conversation."
)

# ---------------------------------------------------------------------------
# Goal templates
# ---------------------------------------------------------------------------

GOAL_RECOMMEND = (
    "Successfully get travel destination recommendations and "
    "follow-up information from the travel agent."
)

GOAL_PLAN = (
    "Evaluate the travel agent's ability to help plan a trip with accurate and helpful information."
)

GOAL_QUICK = "Get a helpful travel recommendation from the agent."

GOAL_THOROUGH = (
    "Conduct a thorough evaluation of the travel agent's knowledge "
    "and planning capabilities across multiple travel topics."
)

# ---------------------------------------------------------------------------
# Test cases: systematic min/max x instruction combinations
# ---------------------------------------------------------------------------

TEST_CASES = [
    # ================================================================
    # A: Implicit min (None) — various max values
    # ================================================================
    {
        "label": "A1: min=None max=3, prose",
        "min_turns": None,
        "max_turns": 3,
        "goal": GOAL_RECOMMEND,
        "instructions": INSTR_PROSE,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "A2: min=None max=5, numbered steps",
        "min_turns": None,
        "max_turns": 5,
        "goal": GOAL_PLAN,
        "instructions": INSTR_NUMBERED,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "A3: min=None max=4, 'turns of phrase'",
        "min_turns": None,
        "max_turns": 4,
        "goal": GOAL_RECOMMEND,
        "instructions": INSTR_TURNS_OF_PHRASE,
        "has_explicit_turn_directive": False,
    },
    # ================================================================
    # B: Low min — tests early-stop prevention
    # ================================================================
    {
        "label": "B1: min=1 max=2, simple",
        "min_turns": 1,
        "max_turns": 2,
        "goal": GOAL_QUICK,
        "instructions": INSTR_SIMPLE,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "B2: min=2 max=4, prose",
        "min_turns": 2,
        "max_turns": 4,
        "goal": GOAL_RECOMMEND,
        "instructions": INSTR_PROSE,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "B3: min=2 max=3, 'take turns'",
        "min_turns": 2,
        "max_turns": 3,
        "goal": GOAL_RECOMMEND,
        "instructions": INSTR_TAKE_TURNS,
        "has_explicit_turn_directive": False,
    },
    # ================================================================
    # C: Medium min — tests deepening strategies
    # ================================================================
    {
        "label": "C1: min=3 max=5, numbered steps",
        "min_turns": 3,
        "max_turns": 5,
        "goal": GOAL_PLAN,
        "instructions": INSTR_NUMBERED,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "C2: min=3 max=6, bullets",
        "min_turns": 3,
        "max_turns": 6,
        "goal": GOAL_THOROUGH,
        "instructions": INSTR_BULLETS,
        "has_explicit_turn_directive": False,
    },
    # ================================================================
    # D: min equals max — forces exact turn count
    # ================================================================
    {
        "label": "D1: min=3 max=3, prose",
        "min_turns": 3,
        "max_turns": 3,
        "goal": GOAL_PLAN,
        "instructions": INSTR_PROSE,
        "has_explicit_turn_directive": False,
    },
    {
        "label": "D2: min=5 max=5, detailed",
        "min_turns": 5,
        "max_turns": 5,
        "goal": GOAL_THOROUGH,
        "instructions": INSTR_DETAILED,
        "has_explicit_turn_directive": False,
    },
    # ================================================================
    # E: Wide gap between min and max
    # ================================================================
    {
        "label": "E1: min=2 max=8, detailed",
        "min_turns": 2,
        "max_turns": 8,
        "goal": GOAL_THOROUGH,
        "instructions": INSTR_DETAILED,
        "has_explicit_turn_directive": False,
    },
    # ================================================================
    # F: Explicit turn directives in instructions
    #    These SHOULD produce turn-count criteria in the judge
    # ================================================================
    {
        "label": "F1: 'at least 3 messages', min=3 max=5",
        "min_turns": 3,
        "max_turns": 5,
        "goal": GOAL_PLAN,
        "instructions": INSTR_EXPLICIT_TURNS.format(n=3),
        "has_explicit_turn_directive": True,
    },
    {
        "label": "F2: 'exactly 4 turns', min=4 max=4",
        "min_turns": 4,
        "max_turns": 4,
        "goal": GOAL_THOROUGH,
        "instructions": INSTR_EXACT_TURNS.format(n=4),
        "has_explicit_turn_directive": True,
    },
    {
        "label": "F3: 'at least 2 messages', min=2 max=3",
        "min_turns": 2,
        "max_turns": 3,
        "goal": GOAL_RECOMMEND,
        "instructions": INSTR_EXPLICIT_TURNS.format(n=2),
        "has_explicit_turn_directive": True,
    },
]


# ---------------------------------------------------------------------------
# Criteria classification
# ---------------------------------------------------------------------------


def _get_criteria(result):
    """Extract structured criteria from goal_evaluation."""
    if not result.goal_evaluation:
        return []
    return result.goal_evaluation.get("criteria_evaluations", [])


def _classify_criteria(criteria):
    """
    Classify criteria as goal-related or turn-count-related.

    Uses two tiers:
    1. Exact phrases: "turn count", "message count", etc.
    2. Combined signal: quantity word + turn/message word in same name
       e.g. "Completed at least 3 turns"

    Returns:
        (goal_criteria, turn_criteria)
    """
    goal_criteria = []
    turn_criteria = []

    exact_signals = [
        "turn count",
        "turn requirement",
        "message count",
        "number of turns",
        "number of messages",
        "minimum turn",
        "minimum message",
    ]
    quantity_words = ["at least", "exactly", "minimum", "completed"]
    turn_words = ["turn", "message", "interaction"]

    for c in criteria:
        name = c.get("criterion", "").lower()

        # Tier 1: exact phrase
        if any(s in name for s in exact_signals):
            turn_criteria.append(c)
            continue

        # Tier 2: quantity word + turn word
        has_qty = any(q in name for q in quantity_words)
        has_tw = any(t in name for t in turn_words)
        if has_qty and has_tw:
            turn_criteria.append(c)
            continue

        goal_criteria.append(c)

    return goal_criteria, turn_criteria


# ---------------------------------------------------------------------------
# Test runner and display
# ---------------------------------------------------------------------------


def run_test(agent, target, case):
    """Run one test case, return (result, checks)."""
    label = case["label"]
    min_t = case.get("min_turns")
    max_t = case.get("max_turns")
    has_directive = case["has_explicit_turn_directive"]

    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"  min_turns={min_t}, max_turns={max_t}")
    print(f"  Explicit turn directive: {has_directive}")
    print(f"{'=' * 70}")

    kwargs = {"target": target, "goal": case["goal"], "instructions": case["instructions"]}
    if max_t is not None:
        kwargs["max_turns"] = max_t
    if min_t is not None:
        kwargs["min_turns"] = min_t

    result = agent.execute_test(**kwargs)

    checks = {}

    # min/max respected
    if min_t is not None:
        checks["min_turns_respected"] = result.turns_used >= min_t
    if max_t is not None:
        checks["max_turns_respected"] = result.turns_used <= max_t

    # Criteria classification
    criteria = _get_criteria(result)
    goal_c, turn_c = _classify_criteria(criteria)
    checks["has_goal_criteria"] = len(goal_c) > 0

    if not has_directive:
        # No turn directive → no spurious turn criterion
        checks["no_spurious_turn_criterion"] = len(turn_c) == 0

    return result, checks


def show_result(result, checks, label):
    """Display one result. Returns True if all checks pass."""
    print(f"\n--- {label} ---")
    print(
        f"  Status: {result.status.value}  |  "
        f"Goal: {'YES' if result.goal_achieved else 'NO'}  |  "
        f"Turns: {result.turns_used}"
        f"{'  |  ' + f'{result.duration_seconds:.1f}s' if result.duration_seconds else ''}"
    )

    criteria = _get_criteria(result)
    if criteria:
        goal_c, turn_c = _classify_criteria(criteria)
        print(f"  Criteria: {len(goal_c)} goal, {len(turn_c)} turn-count")
        for c in criteria:
            met = "MET" if c.get("met") else "NOT MET"
            tag = " [T]" if c in turn_c else ""
            print(f"    [{met}] {c.get('criterion', '?')}{tag}")

    all_ok = True
    for check, passed in checks.items():
        s = "PASS" if passed else "FAIL"
        if not passed:
            all_ok = False
        print(f"  [{s}] {check}")

    return all_ok


def main():
    parser = create_base_parser(
        "Turn budget validation for Penelope",
        "turn_budget_validation.py",
    )
    parser.add_argument(
        "--suite",
        choices=["quick", "full"],
        default="full",
        help="'quick' runs one per category (7 tests), 'full' runs all",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Run single case by prefix (e.g. 'B2', 'F1')",
    )
    args = parser.parse_args()
    if args.quiet:
        args.verbose = False

    agent = PenelopeAgent(enable_transparency=True, verbose=args.verbose)
    target = EndpointTarget(endpoint_id=args.endpoint_id)

    if args.case:
        cases = [c for c in TEST_CASES if c["label"].upper().startswith(args.case.upper())]
        if not cases:
            print(f"No case matching '{args.case}'. Available:")
            for c in TEST_CASES:
                print(f"  {c['label']}")
            return
    elif args.suite == "quick":
        quick = {"A1", "B1", "C1", "D1", "E1", "F1"}
        cases = [c for c in TEST_CASES if c["label"].split(":")[0] in quick]
    else:
        cases = TEST_CASES

    print(f"{'=' * 70}")
    print(f"  TURN BUDGET VALIDATION  |  {len(cases)} tests")
    print(f"  Target: {target.description}")
    print(f"{'=' * 70}")

    results = []
    for case in cases:
        r, ch = run_test(agent, target, case)
        results.append((case, r, ch))

    # Summary
    print(f"\n\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")

    all_ok = True
    for case, r, ch in results:
        if not show_result(r, ch, case["label"]):
            all_ok = False

    passed = sum(1 for _, _, ch in results if all(ch.values()))
    print(f"\n  {passed}/{len(results)} test cases passed all checks")
    print(f"{'=' * 70}")
    print(f"  {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
