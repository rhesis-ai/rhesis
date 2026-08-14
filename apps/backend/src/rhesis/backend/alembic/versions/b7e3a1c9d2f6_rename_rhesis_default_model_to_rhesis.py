"""rename_rhesis_default_model_to_rhesis

Rename the org-onboarded Rhesis-hosted models from "Rhesis Default" /
"Rhesis Default Embedding" to "Rhesis" / "Rhesis Embedding", and update
model_name from "default" to "rhesis" (the composite id changes
from rhesis/default to rhesis/rhesis).

Also strips "No API key required." from the Polyphemus model description.

Revision ID: b7e3a1c9d2f6
Revises: e90c29496562
Create Date: 2026-08-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "b7e3a1c9d2f6"
down_revision: Union[str, None] = "e90c29496562"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        session.execute(
            sa.text(
                """
                UPDATE model
                SET name = 'Rhesis',
                    model_name = 'rhesis',
                    description = 'Rhesis language model.'
                WHERE name = 'Rhesis Default'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                """
            )
        )
        session.execute(
            sa.text(
                """
                UPDATE model
                SET name = 'Rhesis Embedding',
                    model_name = 'rhesis',
                    description = 'Rhesis embedding model.'
                WHERE name = 'Rhesis Default Embedding'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                """
            )
        )
        session.execute(
            sa.text(
                """
                UPDATE model
                SET description = 'Polyphemus adversarial model hosted by Rhesis.'
                WHERE name = 'Rhesis Polyphemus'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'polyphemus'
                  )
                """
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
        session.execute(
            sa.text(
                """
                UPDATE model
                SET name = 'Rhesis Default',
                    model_name = 'default',
                    description = 'Default Rhesis language model.'
                WHERE name = 'Rhesis'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                """
            )
        )
        session.execute(
            sa.text(
                """
                UPDATE model
                SET name = 'Rhesis Default Embedding',
                    model_name = 'default',
                    description = 'Default Rhesis embedding model'
                WHERE name = 'Rhesis Embedding'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                """
            )
        )
        session.execute(
            sa.text(
                """
                UPDATE model
                SET description = 'Polyphemus adversarial model hosted by Rhesis. No API key required.'
                WHERE name = 'Rhesis Polyphemus'
                  AND is_protected = TRUE
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'polyphemus'
                  )
                """
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
