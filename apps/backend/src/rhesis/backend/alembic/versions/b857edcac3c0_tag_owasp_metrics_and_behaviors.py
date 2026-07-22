"""tag_owasp_metrics_and_behaviors

Tag every OWASP metric ("OWASP LLM01: ..." etc.) and OWASP behavior ("OWASP LLM
Top 10", "OWASP Agentic Top 10") with an "OWASP" Tag, per organization, using the
existing generic Tag/TaggedItem system. Entities are matched by their "OWASP"
name prefix. Idempotent: Tag and TaggedItem rows are unique per organization, so
only missing rows are created.

Note: organizations created after this migration don't run it. They get the OWASP
metrics/behaviors via onboarding, but onboarding doesn't create tags yet.

Revision ID: b857edcac3c0
Revises: 30877432d102
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models

# revision identifiers, used by Alembic.
revision: str = "b857edcac3c0"
down_revision: Union[str, None] = "30877432d102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TAG_NAME = "OWASP"
_MODELS = (models.Metric, models.Behavior)


def _owasp_rows(session: Session, model, org_id):
    return session.query(model).filter(
        model.name.like(f"{_TAG_NAME}%"), model.organization_id == org_id
    )


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        orgs = session.execute(
            text(
                "SELECT id, COALESCE(owner_id, user_id) FROM organization WHERE deleted_at IS NULL"
            )
        ).fetchall()
        for org_id, user_id in orgs:
            if not user_id:
                continue
            tag = (
                session.query(models.Tag).filter_by(name=_TAG_NAME, organization_id=org_id).first()
            )
            if not tag:
                tag = models.Tag(name=_TAG_NAME, organization_id=org_id, user_id=user_id)
                session.add(tag)
                session.flush()
            for model in _MODELS:
                for entity in _owasp_rows(session, model, org_id).all():
                    exists = (
                        session.query(models.TaggedItem)
                        .filter_by(
                            tag_id=tag.id,
                            entity_id=entity.id,
                            entity_type=model.__name__,
                            organization_id=org_id,
                        )
                        .first()
                    )
                    if not exists:
                        session.add(
                            models.TaggedItem(
                                tag_id=tag.id,
                                entity_id=entity.id,
                                entity_type=model.__name__,
                                organization_id=org_id,
                                user_id=user_id,
                            )
                        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        for tag in session.query(models.Tag).filter_by(name=_TAG_NAME).all():
            for model in _MODELS:
                ids = [r.id for r in _owasp_rows(session, model, tag.organization_id).all()]
                if ids:
                    session.query(models.TaggedItem).filter(
                        models.TaggedItem.tag_id == tag.id,
                        models.TaggedItem.entity_type == model.__name__,
                        models.TaggedItem.entity_id.in_(ids),
                    ).delete(synchronize_session=False)
            # Drop the tag only if nothing else still uses it.
            if not session.query(models.TaggedItem).filter_by(tag_id=tag.id).first():
                session.delete(tag)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
