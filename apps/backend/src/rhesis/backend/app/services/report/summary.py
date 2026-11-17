"""AI draft of a report's management summary.

Asks the user's generation model, as the requirement review does, for a few sentences
and a recommendation, from the report's live numbers only. Nothing is stored: the
author puts the draft in the summary field, edits it, and saves it like any edit.
"""

import os
from typing import Literal

from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.report.service import compute_metrics
from rhesis.backend.app.utils.user_model_utils import resolve_model


class SummaryUnavailable(Exception):
    """The generation model could not produce a summary."""


class ReportSummaryDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    recommendation: Literal["ready", "ready_with_risks", "not_ready"]


def _render(report: models.Report, metrics) -> str:
    path = os.path.join(os.path.dirname(__file__), "summary.jinja")
    with open(path, "r") as handle:
        template = Template(handle.read())
    return template.render(
        title=report.title,
        endpoint=report.endpoint.name if report.endpoint else "",
        runs=len(metrics.runs),
        versions_differ=metrics.versions_differ,
        totals=metrics.totals,
        requirements=metrics.requirements,
    )


def draft_summary(db: Session, report: models.Report, user: models.User) -> ReportSummaryDraft:
    prompt = _render(report, compute_metrics(db, report))
    try:
        answer = resolve_model(db, user, "generation").generate(prompt, schema=ReportSummaryDraft)
    except Exception as e:
        raise SummaryUnavailable(str(e)) from e
    try:
        return ReportSummaryDraft.model_validate(answer)
    except Exception as e:
        # A provider can swallow its own failure and hand back something else.
        raise SummaryUnavailable(f"The generation model answered with {answer!r}") from e
