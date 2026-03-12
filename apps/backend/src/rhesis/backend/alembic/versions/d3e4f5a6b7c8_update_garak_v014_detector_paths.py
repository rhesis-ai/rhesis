"""update_garak_v014_detector_paths

Updates garak detector class paths in the metric table to match garak v0.14.0
class renames and module moves.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-03-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATH_UPDATES = [
    ("garak.detectors.misleading.MisleadingClaim", "garak.detectors.misleading.MustRefuteClaimKW"),
    ("garak.detectors.lmrc.Lmrc", "garak.detectors.lmrc.Anthro"),
    ("garak.detectors.malwaregen.MalwareGenDetector", "garak.detectors.malwaregen.AnyCode"),
    (
        "garak.detectors.packagehallucination.PackageHallucination",
        "garak.detectors.packagehallucination.PythonPypi",
    ),
    ("garak.detectors.xss.XSSDetector", "garak.detectors.web_injection.XSS"),
    ("garak.detectors.snowball.SnowballDetector", "garak.detectors.snowball.DontStartYes"),
    (
        "garak.detectors.donotanswer.DoNotAnswerDetector",
        "garak.detectors.unsafe_content.ToxicCommentModel",
    ),
    ("garak.detectors.leakreplay.LeakReplayDetector", "garak.detectors.leakreplay.StartsWith"),
    ("garak.detectors.ansiescape.ANSI", "garak.detectors.ansiescape.Escaped"),
    ("garak.detectors.apikey.APIKey", "garak.detectors.apikey.ApiKey"),
    ("garak.detectors.divergence.Repetitive", "garak.detectors.divergence.RepeatDiverges"),
    (
        "garak.detectors.exploitation.ExploitDetector",
        "garak.detectors.exploitation.PythonCodeExecution",
    ),
    (
        "garak.detectors.fileformats.FileFormatDetector",
        "garak.detectors.fileformats.FileIsExecutable",
    ),
]


def upgrade() -> None:
    """Update detector paths to garak v0.14.0 class names."""
    stmt = sa.text(
        "UPDATE metric SET evaluation_prompt = :new_path WHERE evaluation_prompt = :old_path"
    )
    for old_path, new_path in PATH_UPDATES:
        op.execute(stmt, {"new_path": new_path, "old_path": old_path})


def downgrade() -> None:
    """Revert detector paths to pre-v0.14.0 class names."""
    stmt = sa.text(
        "UPDATE metric SET evaluation_prompt = :old_path WHERE evaluation_prompt = :new_path"
    )
    for old_path, new_path in PATH_UPDATES:
        op.execute(stmt, {"old_path": old_path, "new_path": new_path})
