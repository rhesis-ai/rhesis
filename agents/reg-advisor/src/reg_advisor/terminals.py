"""Templated terminal responses (no LLM).

The disclaimer is appended here rather than asked for in a prompt, so it cannot go missing on a
turn where the model is distracted.
"""

from __future__ import annotations

from reg_advisor.knowledge import DISCLAIMER, get_knowledge_base


def _with_disclaimer(body: str) -> str:
    return f"{body.strip()}\n\n{DISCLAIMER}"


def greet_and_explain() -> str:
    """What this agent does, and what it will not do."""
    verified_on = get_knowledge_base().verified_on
    return _with_disclaimer(
        f"""
I help product teams work out which EU and US health-product regulatory regime a product falls
into, what pathway that implies, and what obligations attach.

Tell me what you are building and I will walk the qualification and classification logic with
you: whether it is a device, an IVD, a medicine or none of those; what class it lands in under
the MDR or IVDR; which FDA pathway applies; and where the two systems disagree about the same
product. That last part is usually the most useful — the same clinical decision support tool can
be unregulated in the US and Class IIa in the EU.

I answer only from a loaded knowledge base of regulatory nodes, each carrying its citation and
the date it was checked. This one was verified on {verified_on}. If something is not in there, I
will say so rather than fill the gap.

What I will not do: give legal advice, tell you whether you are compliant, or sign anything off.
Those need a notified body, regulatory counsel, or the regulator itself.

So — what are you building, and what do you claim it does?
"""
    )


def redirect_to_scope() -> str:
    """The question is outside EU/US health-product regulation entirely."""
    return _with_disclaimer(
        """
That sits outside what I cover. I only handle EU and US regulation of health products —
medical devices, IVDs, medicines, biologics, combination products and health software.

If your question is about one of those, tell me what the product does and what claim you make
about it, and I will start from qualification.
"""
    )


def refer_to_expert() -> str:
    """Name what this agent cannot do, and point at the routes that can."""
    return _with_disclaimer(
        """
I am going to stop here and point you elsewhere.

There are three things I do not do, and your question touches at least one of them. I do not
issue compliance determinations — telling you that a product meets a regime is a decision with
legal consequences, and it is not mine to make. I do not help with anything already in front of
a regulator or a court; that needs someone who can see your file and act on your behalf. And I
do not give clinical advice to patients.

The routes that can help:

- A notified body, for EU conformity assessment and classification questions that need a binding
  view. Engage one early — capacity is the dominant EU bottleneck.
- Regulatory counsel or an experienced regulatory consultant, for anything with legal exposure,
  and for borderline or combination-product determinations.
- An FDA Q-Submission (pre-sub), to get FDA's own written feedback before a major submission.
- The relevant national competent authority, for Member State questions and for a formal
  borderline classification request.

I am glad to keep going on the general shape of a regime — what the MDR asks of a Class IIa
device, how the US CDS carve-out is drawn — as background reading. I just cannot apply it to
your product as an answer you rely on.
"""
    )


__all__ = ["greet_and_explain", "redirect_to_scope", "refer_to_expert"]
