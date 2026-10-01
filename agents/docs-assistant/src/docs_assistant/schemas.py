"""Typed shapes for one turn: the route, the model's answer draft, and the response."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Route(StrEnum):
    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    NOT_DOCUMENTED = "not_documented"
    NEEDS_CLARIFICATION = "needs_clarification"
    FALSE_PREMISE = "false_premise"
    OUT_OF_SCOPE = "out_of_scope"
    ACCOUNT_OR_SUPPORT = "account_or_support"
    UNSAFE_OR_INJECTION = "unsafe_or_injection"
    SMALLTALK = "smalltalk"


# The routes the answer agent may pick. The others come from triage and fixed replies.
DraftRoute = Literal[
    "answered", "partially_answered", "not_documented", "false_premise", "needs_clarification"
]


# Draft fields carry no defaults: tool arguments use a strict JSON schema where every field is
# required, and some providers reject optional ones.
class DraftCitation(BaseModel):
    id: str = Field(description="Short id such as 'c1', referenced from claims.")
    url: str = Field(description="A page URL returned by fetch_page, optionally with #anchor.")
    quote: str = Field(description="At least 20 characters copied verbatim from that page.")


class DraftClaim(BaseModel):
    text: str = Field(description="One statement made in the answer.")
    citation_ids: list[str] = Field(description="Ids of the citations that support it.")


class AdaptedCode(BaseModel):
    code: str = Field(description="A code block from answer_md that is not copied verbatim.")
    source_url: str = Field(description="The page you read that it is adapted from.")


class Clarification(BaseModel):
    question: str = Field(description="One short clarifying question, in the user's language.")
    options: list[str] = Field(description="2 to 4 short answers the user can pick from.")


class RelatedPage(BaseModel):
    title: str
    url: str


class AnswerDraft(BaseModel):
    route: DraftRoute
    answer_md: str = Field(description="The answer in markdown, in the user's language.")
    claims: list[DraftClaim]
    citations: list[DraftCitation]
    undocumented: list[str] = Field(
        description="Parts of the question the docs don't cover. Empty when fully answered."
    )
    premise_correction: str | None = Field(
        description="For false_premise: what the question assumed wrongly. Otherwise null."
    )
    related_pages: list[RelatedPage] = Field(
        description="Closest pages to point to, mainly for not_documented. May be empty."
    )
    clarification: Clarification | None = Field(
        description="For needs_clarification only: the question and its options. Otherwise null."
    )
    adapted_code: list[AdaptedCode] = Field(
        description="Every code block in answer_md that you changed from the docs. Usually empty."
    )


# What triage decides about one part of a message. "docs" parts go to the answer agent; the
# others end in a fixed reply.
TriageKind = Literal["docs", "out_of_scope", "account_or_support", "smalltalk", "unsafe"]
Surface = Literal["ui", "sdk", "self_hosting", "both", "unknown"]


class TriagePart(BaseModel):
    standalone_question: str = Field(
        description="The question rewritten to stand on its own, in the user's language."
    )
    kind: TriageKind
    surface: Surface = Field(
        description="Where the user works: the platform UI, the Python SDK, self-hosting, "
        "both, or unknown."
    )
    in_scope_uncertain: bool = Field(
        description="True when you can't tell whether this is about Rhesis."
    )


class TriageDecision(BaseModel):
    parts: list[TriagePart] = Field(description="One entry per separate question, in order.")
    language: str = Field(description="The user's language as a BCP-47 code, e.g. 'en', 'de'.")
    wants_troubleshooting: bool = Field(
        description="For account_or_support: true when docs pages could help the user fix it."
    )
    clarification: Clarification | None = Field(
        description="Only when the message has several readings that need different pages and "
        "different answers, and nothing hints which one is meant. Otherwise null."
    )


class ClaimVerdict(BaseModel):
    index: int = Field(description="The claim number, as given.")
    supported: bool
    reason: str = Field(description="Why not, for unsupported claims; may be empty otherwise.")


class CriticVerdict(BaseModel):
    claims: list[ClaimVerdict]
    route_ok: bool


class NextStep(BaseModel):
    label: str
    url: str


class Citation(BaseModel):
    title: str
    url: str
    heading: str | None = None


class PartResult(BaseModel):
    question: str
    route: Route
    answer_md: str
    citations: list[Citation] = []
    undocumented: list[str] = []
    premise_correction: str | None = None
    related_pages: list[RelatedPage] = []


class TurnResponse(BaseModel):
    conversation_id: str
    turn: int
    route: Route
    response: str
    answer_md: str
    citations: list[Citation]
    undocumented: list[str] = []
    premise_correction: str | None = None
    related_pages: list[RelatedPage] = []
    parts: list[PartResult] = []
    clarification: Clarification | None = None
    next_steps: list[NextStep] = []
    surface: Surface = "unknown"
    language: str = "en"
    docs_as_of: datetime
    docs_stale: bool = False
    limits_hit: list[str] = []
    answer_id: str
