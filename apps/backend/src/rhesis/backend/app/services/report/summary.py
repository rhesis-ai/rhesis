"""AI draft of a report's management summary.

Asks the user's generation model, as the requirement review does, for a few sentences
and a recommendation, from the report's live numbers only. Nothing is stored: the
author puts the draft in the summary field, edits it, and saves it like any edit.
"""

import os
from typing import Literal, Optional

from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.report.service import compute_metrics
from rhesis.backend.app.utils.user_model_utils import resolve_model


class SummaryUnavailable(Exception):
    """The generation model could not produce a summary."""


class ReportSummaryText(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)


class ReportSummaryDraft(ReportSummaryText):
    recommendation: Literal["ready", "ready_with_risks", "not_ready"]


class ReportSummaryAnswer(ReportSummaryText):
    """What the route returns: no recommendation outside a release report."""

    recommendation: Optional[Literal["ready", "ready_with_risks", "not_ready"]] = None


def _render(report: models.Report, metrics) -> str:
    path = os.path.join(os.path.dirname(__file__), "summary.jinja")
    with open(path, "r") as handle:
        template = Template(handle.read())
    return template.render(
        title=report.title,
        is_release=report.is_release,
        endpoint=report.endpoint.name if report.endpoint else "",
        runs=len(metrics.runs),
        versions_differ=metrics.versions_differ,
        rule=metrics.result_rule,
        totals=metrics.totals,
        requirements=metrics.requirements,
    )


def draft_summary(db: Session, report: models.Report, user: models.User) -> ReportSummaryAnswer:
    prompt = _render(report, compute_metrics(db, report))
    schema = ReportSummaryDraft if report.is_release else ReportSummaryText
    try:
        answer = resolve_model(db, user, "generation").generate(prompt, schema=schema)
    except Exception as e:
        raise SummaryUnavailable(str(e)) from e
    try:
        return ReportSummaryAnswer.model_validate(schema.model_validate(answer).model_dump())
    except Exception as e:
        # A provider can swallow its own failure and hand back something else.
        raise SummaryUnavailable(f"The generation model answered with {answer!r}") from e
