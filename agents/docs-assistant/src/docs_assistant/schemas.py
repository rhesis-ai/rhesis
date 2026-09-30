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
DraftRoute = Literal["answered", "partially_answered", "not_documented", "false_premise"]


# Draft fields carry no defaults: tool arguments use a strict JSON schema where every field is
# required, and some providers reject optional ones.
class DraftCitation(BaseModel):
    id: str = Field(description="Short id such as 'c1', referenced from claims.")
    url: str = Field(description="A page URL returned by fetch_page, optionally with #anchor.")
    quote: str = Field(description="At least 20 characters copied verbatim from that page.")


class DraftClaim(BaseModel):
    text: str = Field(description="One statement made in the answer.")
    citation_ids: list[str] = Field(description="Ids of the citations that support it.")


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


class Citation(BaseModel):
    title: str
    url: str
    heading: str | None = None


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
    docs_as_of: datetime
    docs_stale: bool = False
    limits_hit: list[str] = []
    answer_id: str
