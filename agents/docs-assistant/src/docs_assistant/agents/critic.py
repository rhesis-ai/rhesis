"""The critic: a fresh model call that checks each claim against the text it cites.

The code checks prove a quote is on the page; they can't tell whether the quote supports the
claim. The critic sees each claim with its quotes and the text around them, and nothing else,
so it can't be talked into agreeing with the draft. It has no tools, so `output_type` is safe.
"""

from __future__ import annotations

from agents import Agent, Model, ModelSettings

from docs_assistant.corpus.parser import Page, split_anchor
from docs_assistant.grounding import normalize
from docs_assistant.schemas import AnswerDraft, CriticVerdict

CONTEXT_CHARS = 600

INSTRUCTIONS = """\
You check answers written from the Rhesis documentation. For each numbered claim you get the
quotes it cites and the documentation text around each quote.

For every claim, decide whether the cited text supports it:
- supported: the claim says what the text says. Rewording is fine; so is a claim that sums up
  the text faithfully.
- not supported: the claim adds facts, numbers, names, parameters or steps the text doesn't
  contain, overstates it, or contradicts it.

Give a short reason for every claim you mark unsupported. Then set route_ok: false only when
the route clearly doesn't fit (e.g. "answered" while a claim says the docs don't cover
something). Judge only against the text given; don't use outside knowledge.
"""


def build_critic(model: Model, settings: ModelSettings) -> Agent:
    return Agent(
        name="docs_critic",
        instructions=INSTRUCTIONS,
        model=model,
        model_settings=settings,
        output_type=CriticVerdict,
    )


def critic_input(draft: AnswerDraft, ledger: dict[str, Page]) -> str:
    """Each claim with its quotes and the page text around them, built in code."""
    by_id = {c.id: c for c in draft.citations}
    blocks = [f"Route: {draft.route}"]
    for n, claim in enumerate(draft.claims, start=1):
        lines = [f"Claim {n}: {claim.text}"]
        for citation_id in claim.citation_ids:
            citation = by_id.get(citation_id)
            if citation is None:
                continue
            page = ledger.get(split_anchor(citation.url)[0])
            context = surrounding_text(page.body, citation.quote) if page else ""
            lines.append(f'  Quote: "{citation.quote}"\n  Context: {context}')
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def surrounding_text(body: str, quote: str, chars: int = CONTEXT_CHARS) -> str:
    """The quote with up to `chars` characters on each side. Quotes that only match after
    normalizing are located in the normalized text."""
    start = body.find(quote.strip())
    text, needle = body, quote.strip()
    if start < 0:
        text, needle = normalize(body), normalize(quote)
        start = text.find(needle)
    if start < 0:
        return ""
    return text[max(start - chars, 0) : start + len(needle) + chars].strip()


def unsupported(verdict: CriticVerdict, claim_count: int) -> dict[int, str]:
    """Zero-based indexes of the claims the critic vetoed, with its reasons."""
    return {
        v.index - 1: v.reason or "not supported by the cited text"
        for v in verdict.claims
        if not v.supported and 1 <= v.index <= claim_count
    }


def feedback(draft: AnswerDraft, vetoed: dict[int, str], route_ok: bool) -> str:
    lines = [
        "Your previous answer was:",
        draft.answer_md,
        "",
        "A reviewer checked it against the cited text and found problems:",
    ]
    for index, reason in sorted(vetoed.items()):
        lines.append(f'- claim "{draft.claims[index].text}": {reason}')
    if not route_ok:
        lines.append(f"- the route {draft.route} doesn't fit the answer")
    lines.append(
        "Fix these: support each claim with a quote that says it, or remove the claim (list it "
        "in undocumented if the docs don't cover it). Then call submit_answer again."
    )
    return "\n".join(lines)
