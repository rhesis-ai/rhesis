"""Templated terminal responses (no LLM)."""

from __future__ import annotations

from dr_rhesis.state import DrRhesisState


def greet_and_explain() -> str:
    return (
        "Hello! I'm a visit-preparation assistant. I help you organize your symptom "
        "history before a doctor's appointment — one question at a time — and then "
        "produce a timeline and a short list of questions to ask your clinician.\n\n"
        "I don't diagnose or recommend treatment. If you describe a symptom you'd like "
        "to prepare for, we can get started."
    )


def redirect_to_scope() -> str:
    return (
        "I'm here to help you prepare for a medical visit, not to diagnose or "
        "prescribe. I can help you organize what you're experiencing and suggest "
        "questions to ask your clinician.\n\n"
        "If you'd like, tell me about a symptom or concern you're planning to "
        "discuss at your appointment."
    )


def escalate() -> str:
    return (
        "What you're describing may need urgent medical attention. Please call "
        "emergency services (911 in the US) or go to the nearest emergency "
        "department right away.\n\n"
        "If you're not in immediate danger but feel you need urgent care, contact "
        "your clinician's after-hours line or an urgent-care clinic.\n\n"
        "I can't safely continue visit preparation when urgent symptoms are "
        "present — a clinician needs to evaluate you directly."
    )


def terminal_reply(intent: str, state: DrRhesisState) -> tuple[str, DrRhesisState]:
    """Return a terminal response and updated state for non-gathering intents."""
    from dr_rhesis.state import Phase

    updated = state.model_copy(deep=True)
    if intent == "emergency":
        updated.phase = Phase.ESCALATED
        updated.red_flag = True
        return escalate(), updated
    if intent in {"greeting", "meta"}:
        return greet_and_explain(), updated
    if intent == "out_of_scope":
        return redirect_to_scope(), updated
    raise ValueError(f"Not a terminal intent: {intent}")


__all__ = ["escalate", "greet_and_explain", "redirect_to_scope", "terminal_reply"]
