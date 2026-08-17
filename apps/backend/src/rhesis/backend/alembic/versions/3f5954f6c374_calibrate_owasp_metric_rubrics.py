"""calibrate_owasp_metric_rubrics

Pushes the calibrated evaluation_prompt/evaluation_steps/reasoning/
evaluation_examples text -- plus a context_required correction on two ASI
metrics -- for the 20 OWASP LLM Top 10 / Agentic Top 10 judge metrics from
initial_data.json to organizations that already have these rows.

initial_data.json is only read once, at brand-new-org onboarding or via the
38ed899b9f41 sync migration. Editing it directly changes nothing for an org
that already has these metrics seeded, since nothing re-reads the JSON for
existing rows -- this migration is the mechanism that actually pushes the
calibrated rubric text to those rows.

Guarded per-row rather than with a plain `WHERE name = :name` (the
a6a7196f4949 precedent for a single short description field): each of these
20 rubrics is several KB of prompt/steps/reasoning/examples text, so
embedding the full pre-calibration text as literal comparison values here
would make this file enormous. Instead, each row's current fields are hashed
(sha256 over evaluation_prompt/evaluation_steps/reasoning/
evaluation_examples/context_required) and compared against the known hash of
the original, pre-calibration text -- a row that still matches is safe to
update; an org that has since customized its copy through the UI hashes to
something else and is left alone.

Revision ID: 3f5954f6c374
Revises: d52329dc7e4e
Create Date: 2026-08-15
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from rhesis.backend.alembic.utils.metric_sync import load_metrics_from_initial_data
from rhesis.backend.app import models

# revision identifiers, used by Alembic.
revision: str = "3f5954f6c374"
down_revision: Union[str, None] = "d52329dc7e4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# sha256 of "\x00".join([evaluation_prompt, evaluation_steps, reasoning,
# evaluation_examples, str(bool(context_required))]) for each metric's
# pre-calibration text, as it stood in initial_data.json before this
# calibration round (git commit 83f95973d).
ORIGINAL_HASHES: Dict[str, str] = {
    "OWASP ASI01: Agent Goal Hijack": (
        "5b95518994316daf5e8d109add118252e65f884640284fedf3b4f64be969ee28"
    ),
    "OWASP ASI02: Tool Misuse and Exploitation": (
        "7d414c06dbee149867eeb8ee35422d2d09ae78b3ae6625879268128f42193a41"
    ),
    "OWASP ASI03: Identity and Privilege Abuse": (
        "662efb9af48a9ce5b66762cb4d6c7294a635da9b400011d99f63cec74f09a37b"
    ),
    "OWASP ASI04: Agentic Supply Chain Vulnerabilities": (
        "cf7401b5fe99e0dbbf1501638f418da34734528cc9ebd7bbf525ac34897e07dd"
    ),
    "OWASP ASI05: Unexpected Code Execution (RCE)": (
        "dc6d592b0513bea3b7c6f5146a86baa20a489362f5d688e510fb17069e2a8a2b"
    ),
    "OWASP ASI06: Memory & Context Poisoning": (
        "b06c263b353b0a188777eecb2361bb4e3f2177ff8ce664a561d011217e6475fc"
    ),
    "OWASP ASI07: Insecure Inter-Agent Communication": (
        "afbc026decb52d089f5d8fcbcca7bf73c74e55bac3d3ce69d8b36679293ae5d9"
    ),
    "OWASP ASI08: Cascading Failures": (
        "760440d4f6618d1ba577411125b3aff086cb59099b17eaf5ff9bf62adf921801"
    ),
    "OWASP ASI09: Human-Agent Trust Exploitation": (
        "a51e4d241d766d0fa65191c486d6b53960bb9078242d51c94dc71007ef38e434"
    ),
    "OWASP ASI10: Rogue Agents": (
        "218632d3e772912572d1c2b3b74a04d45009273d1e5c90ed2ba99fe378d2037a"
    ),
    "OWASP LLM01: Prompt Injection": (
        "b863c70f44a6d87eec5d72d835a4dae8ced82d4c7829e9a4cc458b69fe19455c"
    ),
    "OWASP LLM02: Sensitive Information Disclosure": (
        "770bc6f06ab132f31c2ad024ba1b59a44f6ea9e6839803ce793f5c37417b3cc2"
    ),
    "OWASP LLM03: Supply Chain": (
        "a9c4ec6a244a8aceb9d72049f8673f8ef3c4f8b2f37eeba4985f5353aa5a5425"
    ),
    "OWASP LLM04: Data and Model Poisoning": (
        "960af98848ffca12768cc75a66f5ed3c580c9867666df6e97a844301c45041d5"
    ),
    "OWASP LLM05: Improper Output Handling": (
        "b183edb6cd41585d65014cec13dfa157bf63208dbbcc4d011b76f8a392a7f8a7"
    ),
    "OWASP LLM06: Excessive Agency": (
        "57f6a80fe45efed87cdf7ec2740a226a0345fdf2402cd5e66210f9ce346d528e"
    ),
    "OWASP LLM07: System Prompt Leakage": (
        "4de7b63b9d4474e17a9d927dac86e0d21bb383e6de8b2880857a57cf3d288b00"
    ),
    "OWASP LLM08: Vector and Embedding Weaknesses": (
        "ca509d0fc44f27f967aa3bda8123015fbe40331b40af37724b2994bba385bffb"
    ),
    "OWASP LLM09: Misinformation": (
        "a6e2d7c4f41eec3d90d8165fcd65d93f98d79ff186e8e15f26d68dca9276583a"
    ),
    "OWASP LLM10: Unbounded Consumption": (
        "4fdd8dc94054d8bc0723afde23dd8fd50029f7c141ca3c06f09a7c52ac0f0cb9"
    ),
}


def _field_hash(
    evaluation_prompt: str | None,
    evaluation_steps: str | None,
    reasoning: str | None,
    evaluation_examples: str | None,
    context_required: bool | None,
) -> str:
    parts = [
        evaluation_prompt or "",
        evaluation_steps or "",
        reasoning or "",
        evaluation_examples or "",
        str(bool(context_required)),
    ]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def _new_metric_fields(metric_item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evaluation_prompt": metric_item["evaluation_prompt"],
        "evaluation_steps": metric_item.get("evaluation_steps"),
        "reasoning": metric_item.get("reasoning"),
        "evaluation_examples": metric_item.get("evaluation_examples"),
        "context_required": metric_item.get("context_required", False),
    }


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    new_metrics_by_name = {
        m["name"]: _new_metric_fields(m)
        for m in load_metrics_from_initial_data()
        if m["name"] in ORIGINAL_HASHES
    }

    rows = (
        session.query(models.Metric)
        .filter(
            models.Metric.name.in_(ORIGINAL_HASHES.keys()),
            models.Metric.deleted_at.is_(None),
        )
        .all()
    )

    updated = 0
    skipped_customized = 0
    skipped_unmatched = 0

    for row in rows:
        new_fields = new_metrics_by_name.get(row.name)
        if new_fields is None:
            # Name in ORIGINAL_HASHES but not in the current initial_data.json --
            # shouldn't happen, but don't touch a row we have nothing to apply.
            skipped_unmatched += 1
            continue

        current_hash = _field_hash(
            row.evaluation_prompt,
            row.evaluation_steps,
            row.reasoning,
            row.evaluation_examples,
            row.context_required,
        )
        if not hmac.compare_digest(current_hash, ORIGINAL_HASHES[row.name]):
            skipped_customized += 1
            continue

        row.evaluation_prompt = new_fields["evaluation_prompt"]
        row.evaluation_steps = new_fields["evaluation_steps"]
        row.reasoning = new_fields["reasoning"]
        row.evaluation_examples = new_fields["evaluation_examples"]
        row.context_required = new_fields["context_required"]
        updated += 1

    session.commit()
    session.close()

    print(
        f"Calibrated OWASP metric rubrics: updated {updated} row(s), "
        f"skipped {skipped_customized} customized, {skipped_unmatched} unmatched"
    )


def downgrade() -> None:
    # Informational rubric-text change, not a structural one -- no downgrade
    # path, matching the a6a7196f4949 precedent.
    pass
