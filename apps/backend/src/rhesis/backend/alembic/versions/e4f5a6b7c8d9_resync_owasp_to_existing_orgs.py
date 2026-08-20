"""resync_owasp_to_existing_orgs

38ed899b9f41 syncs OWASP behaviors and metrics to existing organizations,
and b857edcac3c0 tags them.  Both migrations run before 491519fd3010
(rename behavior -> requirement), so on a database that encounters the
full chain for the first time both are skipped by the "no requirement
table yet" guard added in PR #2512.

New orgs still get the data via onboarding, but every org that existed
before v0.13.0 is left without OWASP metrics.

This migration re-runs the same sync + tag logic, now positioned after
the rename and after the calibrated-rubric push, so the requirement
table exists and the latest initial_data.json rubrics are picked up.

Revision ID: e4f5a6b7c8d9
Revises: a4b5c6d7e8f9
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from rhesis.backend.alembic.utils.metric_sync import (
    _list_organizations_with_owner,
    load_metrics_from_initial_data,
    load_requirements_from_initial_data,
    sync_metrics_to_organizations,
    sync_requirements_to_organizations,
)
from rhesis.backend.app import models

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWASP_PREFIX = "OWASP"
_TAG_NAME = "OWASP"


def _owasp_requirement_names() -> list[str]:
    return [
        r["name"]
        for r in load_requirements_from_initial_data()
        if r["name"].startswith(_OWASP_PREFIX)
    ]


def _owasp_metric_names() -> list[str]:
    return [
        m["name"] for m in load_metrics_from_initial_data() if m["name"].startswith(_OWASP_PREFIX)
    ]


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        requirement_names = _owasp_requirement_names()
        metric_names = _owasp_metric_names()

        # Sync requirements first so metric -> requirement associations resolve.
        # commit_per_org: this runs at container start via `alembic upgrade head`,
        # and on an install with hundreds of orgs a single transaction is both slow
        # and all-or-nothing — a pod restart part-way through would otherwise discard
        # every org's work and begin again from zero. The syncs skip names that
        # already exist, so committing per org makes a killed run resume instead.
        sync_requirements_to_organizations(
            session=session,
            requirement_names=requirement_names,
            verbose=True,
            commit=False,
            commit_per_org=True,
        )

        sync_metrics_to_organizations(
            session=session,
            metric_names=metric_names,
            verbose=True,
            commit=False,
            commit_per_org=True,
        )

        # Tag OWASP metrics and behaviors (mirrors b857edcac3c0).
        orgs = _list_organizations_with_owner(session)
        for org_id, user_id in orgs:
            tag = (
                session.query(models.Tag).filter_by(name=_TAG_NAME, organization_id=org_id).first()
            )
            if not tag:
                tag = models.Tag(name=_TAG_NAME, organization_id=org_id, user_id=user_id)
                session.add(tag)
                session.flush()
            # One query for every already-tagged pair in this org, instead of a
            # TaggedItem lookup per entity. At ~30 OWASP entities per org that is
            # ~30 statements down to 1.
            already_tagged = {
                (ti.entity_id, ti.entity_type)
                for ti in session.query(models.TaggedItem)
                .filter_by(tag_id=tag.id, organization_id=org_id)
                .all()
            }

            for model_cls in (models.Metric, models.Requirement):
                rows = (
                    session.query(model_cls)
                    .filter(
                        model_cls.name.like(f"{_OWASP_PREFIX}%"),
                        model_cls.organization_id == org_id,
                    )
                    .all()
                )
                for entity in rows:
                    if (entity.id, model_cls.__name__) not in already_tagged:
                        session.add(
                            models.TaggedItem(
                                tag_id=tag.id,
                                entity_id=entity.id,
                                entity_type=model_cls.__name__,
                                organization_id=org_id,
                                user_id=user_id,
                            )
                        )
                        already_tagged.add((entity.id, model_cls.__name__))

            # Same rationale as commit_per_org above: keep this resumable and stop
            # the identity map growing across every org.
            session.commit()
            session.expunge_all()

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    # Idempotent sync; no structural changes to reverse.
    pass
