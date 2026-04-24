"""set_rhesis_default_embedding_model_dimension

Set dimension=768 on all org default Rhesis embedding model rows
(name = Rhesis Default Embedding, provider rhesis)
since it's the default dimension of vertex text-embedding-005.

Revision ID: c2e4f8a91b0d
Revises: f3fc3b9e444f9a32
Create Date: 2026-04-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "c2e4f8a91b0d"
down_revision: Union[str, None] = "f3fc3b9e444f9a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    dim = 768  # Default dimension of vertex text-embedding-005
    try:
        result = session.execute(
            sa.text(
                """
                UPDATE model
                SET dimension = :dim
                WHERE name = 'Rhesis Default Embedding'
                  AND model_type = 'embedding'
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                """
            ),
            {"dim": dim},
        )
        session.commit()
        print(f"✓ Set dimension={dim} on {result.rowcount} Rhesis Default Embedding model(s)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    """Clear dimension only where it was set to the default by this migration."""
    bind = op.get_bind()
    session = Session(bind=bind)
    dim = 768  # Default dimension of vertex text-embedding-005
    try:
        result = session.execute(
            sa.text(
                """
                UPDATE model
                SET dimension = NULL
                WHERE name = 'Rhesis Default Embedding'
                  AND model_type = 'embedding'
                  AND provider_type_id IN (
                      SELECT id FROM type_lookup
                      WHERE type_name = 'ProviderType' AND type_value = 'rhesis'
                  )
                  AND dimension = :dim
                """
            ),
            {"dim": dim},
        )
        session.commit()
        print(f"✓ Cleared dimension on {result.rowcount} Rhesis Default Embedding model(s)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
