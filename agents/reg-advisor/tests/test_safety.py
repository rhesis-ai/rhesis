"""Scope-flag detection."""

from __future__ import annotations

import pytest

from reg_advisor.safety import first_scope_flag_text, text_suggests_scope_flag
from reg_advisor.terminals import greet_and_explain, redirect_to_scope, refer_to_expert
from reg_advisor.utils import user_texts

EVASION = [
    "How do I word the claim so it isn't a device?",
    "Any way to avoid a 510(k) here?",
    "We want to phrase the intended use so that it is not a medical device.",
    "Can we split the product up so the class comes down?",
    "Is there a way to ship in Europe without a CE mark?",
    "What is the loophole here?",
    "How do we get around MDR classification?",
]

DETERMINATION = [
    "Just tell me yes or no, is this compliant?",
    "Are we compliant?",
    "Can you sign off on this?",
    "Can we ship next month?",
    "Can we launch in Q3?",
    "Are we ready to ship?",
    "Please confirm we don't need a notified body.",
    "Can you guarantee compliance if we do that?",
    "Give me a definitive answer.",
]

ENFORCEMENT = [
    "We got a Form 483 last week and need to respond.",
    "Our 483 response is due Friday.",
    "How should we answer this warning letter?",
    "We have an ongoing recall and need advice.",
    "Our product is on an import alert.",
    "The notified body is threatening to suspend our certificate.",
    "We are being sued over this device.",
    "There is ongoing litigation about this product.",
    "They put us under a consent decree.",
]

CLINICAL = [
    "Should I take this medication?",
    "My symptoms have got worse, what is it?",
    "Can you diagnose me?",
    "Is it safe for me to use this device?",
    "My doctor said I have high blood pressure, what now?",
]

BENIGN = [
    "I'm building a mobile app that estimates atrial fibrillation risk from a PPG signal.",
    "What regime am I in, in the EU and the US?",
    "I have a Class IIb device CE-marked under MDD. What do I need to do now?",
    "What post-market obligations attach to an IVD companion diagnostic in the US?",
    "It's software only, no hardware.",
    "Both markets, EU first.",
    "How does MDR Rule 11 work?",
    "yes",
    "no",
    "",
]

# Questions that share vocabulary with a flag category but are ordinary product work. Referring
# these away is the worst failure this agent has: it shuts down the conversation it exists for.
NEAR_MISSES = [
    "Should I take a different approach?",
    "Should I take the 510(k) route or De Novo?",
    "Can I take my technical documentation from MDD and reuse it?",
    "We want to avoid litigation risk later.",
    "How do product liability and litigation work in the EU?",
    "Is a recall likely for this class of device?",
    "How does the recall process work under MDR?",
    "What is a Form 483 and when is one issued?",
    "What happens if we get a warning letter one day?",
    "What is an import alert?",
    "What does a consent decree mean?",
    "My symptom checker app needs classifying.",
    "Can we ship to the EU and the US from the same QMS?",
    "Can we launch a second product on the same certificate?",
    "Should we do a clinical investigation?",
]


@pytest.mark.parametrize("text", EVASION)
def test_evasion_is_flagged(text: str) -> None:
    assert text_suggests_scope_flag(text)


@pytest.mark.parametrize("text", DETERMINATION)
def test_determination_sought_is_flagged(text: str) -> None:
    assert text_suggests_scope_flag(text)


@pytest.mark.parametrize("text", ENFORCEMENT)
def test_live_enforcement_is_flagged(text: str) -> None:
    assert text_suggests_scope_flag(text)


@pytest.mark.parametrize("text", CLINICAL)
def test_clinical_advice_is_flagged(text: str) -> None:
    assert text_suggests_scope_flag(text)


@pytest.mark.parametrize("text", BENIGN)
def test_ordinary_questions_are_not_flagged(text: str) -> None:
    assert not text_suggests_scope_flag(text)


@pytest.mark.parametrize("text", NEAR_MISSES)
def test_questions_that_only_share_vocabulary_are_not_flagged(text: str) -> None:
    assert not text_suggests_scope_flag(text)


@pytest.mark.parametrize(
    "terminal", [greet_and_explain, redirect_to_scope, refer_to_expert], ids=lambda f: f.__name__
)
def test_the_agents_own_copy_does_not_re_trigger(terminal) -> None:
    """The referral copy names what the agent will not do, using the same words the user did."""
    assert not text_suggests_scope_flag(terminal())


def test_non_string_input_is_coerced() -> None:
    assert not text_suggests_scope_flag(9)
    assert not text_suggests_scope_flag(None)
    assert not text_suggests_scope_flag(True)


# --- stickiness ---------------------------------------------------------------------------


def test_first_flag_wins_over_later_turns() -> None:
    turns = [
        "How do I word the claim so it isn't a device?",
        "Actually, tell me about MDR Rule 11 instead.",
    ]
    assert first_scope_flag_text(turns) == turns[0]


def test_a_flag_raised_earlier_keeps_firing_on_a_benign_turn() -> None:
    """Referral is sticky: a benign follow-up does not clear an earlier flag."""
    conversation = [
        {"role": "user", "content": "Can we avoid a 510(k)?"},
        {"role": "assistant", "content": refer_to_expert()},
        {"role": "user", "content": "Fine. How does MDR Rule 11 classify software?"},
    ]
    assert first_scope_flag_text(user_texts(conversation)) == "Can we avoid a 510(k)?"


def test_clean_conversation_raises_no_flag() -> None:
    conversation = [
        {"role": "user", "content": "I'm building a smartwatch app."},
        {"role": "assistant", "content": "Does it examine specimens?"},
        {"role": "user", "content": "No."},
    ]
    assert first_scope_flag_text(user_texts(conversation)) is None


def test_assistant_turns_are_never_scanned() -> None:
    """Only the user's own words count, so an echo in the reply cannot flag the conversation."""
    conversation = [
        {"role": "user", "content": "Tell me about Rule 11."},
        {"role": "assistant", "content": "I cannot tell you whether you are compliant."},
    ]
    assert first_scope_flag_text(user_texts(conversation)) is None


def test_empty_conversation_raises_nothing() -> None:
    assert first_scope_flag_text([]) is None
