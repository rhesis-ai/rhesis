"""Derives the evaluation contract for a multi-turn test.

Runs lazily: the first execution of a test interprets it and stores the result on
``Test.test_metadata``, keyed by a digest of the authored fields. Later runs reuse it and cost
nothing, so a verdict cannot drift between two runs of an unedited test. Editing any authored
field changes the digest and triggers re-interpretation.

A test we cannot interpret confidently must not produce a verdict -- see ``contract_usability``.
Falling back to scoring the raw goal would reintroduce exactly the bug the contract exists to
fix, and would do it silently.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

import jinja2
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.schemas.evaluation_contract import (
    CONTRACT_VERSION,
    EvaluationContract,
    EvaluationContractStatus,
    InterpretedContract,
    authored_fields_digest,
    read_contract,
    store_contract,
)
from rhesis.backend.app.utils.user_model_utils import ensure_language_model, get_evaluation_model
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)

_TEMPLATE_NAME = "test_interpretation.jinja2"

#: Interpretation decides which direction a test is scored in, so it is run at temperature 0 --
#: the same test must not be read one way today and the other way tomorrow.
_TEMPERATURE = 0.0

#: Below this, the interpreter is signalling that it could plausibly read the test either way.
#: Scoring anyway would produce a confident verdict from an admitted coin-flip.
MIN_CONFIDENCE = 0.5

#: Stamped by us, never accepted from the interpreter model. See ``interpret_test_configuration``.
_PROVENANCE_FIELDS = frozenset(
    {"interpreted_from", "interpreted_at", "interpreter_model", "contract_version"}
)


def _template() -> jinja2.Template:
    template_dir = Path(__file__).parent.parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        autoescape=False,  # plain-text prompt, not markup
    )
    return env.get_template(_TEMPLATE_NAME)


def is_multi_turn_config(test_configuration: Optional[Mapping[str, Any]]) -> bool:
    """Whether this config is a multi-turn test.

    Presence of ``goal`` is how the rest of the codebase decides this -- see
    ``schemas/validators.py``.
    """
    return isinstance(test_configuration, Mapping) and "goal" in test_configuration


def interpret_test_configuration(
    test_configuration: Mapping[str, Any],
    *,
    model: BaseLLM,
    requirement: Optional[str] = None,
    category: Optional[str] = None,
    topic: Optional[str] = None,
) -> EvaluationContract:
    """Interpret authored fields into a contract. Does not touch the database.

    Returns an all-defaults contract on failure rather than raising: an unusable contract is
    already the fail-safe state, and callers check usability regardless.
    """
    prompt = _template().render(
        goal=test_configuration.get("goal") or "",
        instructions=test_configuration.get("instructions") or "",
        restrictions=test_configuration.get("restrictions") or "",
        scenario=test_configuration.get("scenario") or "",
        requirement=requirement,
        category=category,
        topic=topic,
    )

    try:
        raw = model.generate(
            prompt=prompt,
            schema=InterpretedContract,
            temperature=_TEMPERATURE,
        )
        interpreted = InterpretedContract.model_validate(raw)

        # ``InterpretedContract`` allows extra keys, so a model that echoes a provenance field
        # would collide with the ones set here and raise TypeError. Provenance is ours to stamp,
        # never the model's to supply, so drop any it invented.
        semantic = {
            key: value
            for key, value in interpreted.model_dump().items()
            if key not in _PROVENANCE_FIELDS
        }

        return EvaluationContract(
            **semantic,
            interpreted_from=authored_fields_digest(test_configuration),
            interpreted_at=datetime.now(timezone.utc).isoformat(),
            interpreter_model=getattr(model, "model_name", None) or type(model).__name__,
            contract_version=CONTRACT_VERSION,
        )
    except Exception:
        logger.exception("Test interpretation failed; returning an unusable contract")
        return EvaluationContract()


def contract_usability(contract: EvaluationContract) -> Tuple[bool, str]:
    """Whether a contract may be used to score a run, and why not if it may not.

    The reason is surfaced to the user on an errored result, so it has to read as an
    explanation of what to fix, not an internal code.
    """
    if not contract.interpreted_from:
        return False, "This test could not be interpreted, so it has nothing to be scored against."
    if not contract.is_scorable:
        return False, (
            "No required or prohibited behaviour could be identified for the target. "
            "State what the target must or must not do in the goal or restrictions."
        )
    if contract.confidence < MIN_CONFIDENCE:
        return False, (
            f"The test's wording was ambiguous (interpretation confidence "
            f"{contract.confidence:.2f}). Rephrase the goal or restrictions to say plainly what "
            f"the target must or must not do."
        )
    return True, ""


def contract_status(test: Any) -> EvaluationContractStatus:
    """Describe a test's stored interpretation without interpreting it.

    A pure read: the review panel must not trigger an LLM call just by being opened.

    ``test`` is typed ``Any`` on purpose: besides a real ORM ``Test`` row, callers pass
    ephemeral test-like objects for trial/in-place execution (see
    ``app/services/test_execution.py``'s ``InlineTest``) that carry no ``test_metadata``
    attribute at all. ``getattr`` tolerates that instead of raising.
    """
    config = test.test_configuration or {}
    if not is_multi_turn_config(config):
        return EvaluationContractStatus(reason="Interpretation applies to multi-turn tests only.")

    contract = read_contract(getattr(test, "test_metadata", None))
    if not contract.interpreted_from:
        return EvaluationContractStatus(reason="This test has not been interpreted yet.")

    usable, reason = contract_usability(contract)
    return EvaluationContractStatus(
        contract=contract,
        interpreted=True,
        is_current=contract.is_current_for(config),
        usable=usable,
        reason=reason,
    )


def ensure_contract(
    db: Session,
    test: Any,
    *,
    user_id: Optional[str] = None,
    model: Optional[Union[str, BaseLLM]] = None,
    force: bool = False,
) -> EvaluationContract:
    """Return the test's contract, interpreting and storing it if it is missing or stale.

    Mutates ``test.test_metadata`` but does not commit -- the caller owns the transaction, as
    with ``services/review_override.py``. A missed commit only costs a repeated interpretation
    on the next run.

    ``test`` is typed ``Any`` on purpose: trial/in-place execution passes an ephemeral,
    unpersisted test-like object (``app/services/test_execution.py``'s ``InlineTest``) that has
    no ``test_metadata`` attribute and was never mapped by the ORM. For those, this still
    derives a contract correctly; it just can't be cached (there's no stable row to cache it
    on), and the mutation below is a plain, harmless attribute set rather than a tracked ORM
    change -- which is why ``flag_modified`` is skipped for anything that isn't a real ``Test``.
    """
    config = test.test_configuration or {}
    if not is_multi_turn_config(config):
        return EvaluationContract()

    existing = read_contract(getattr(test, "test_metadata", None))
    if not force and existing.is_current_for(config):
        return existing

    resolved = model if isinstance(model, BaseLLM) else None
    if resolved is None:
        source = (
            model if model is not None else get_evaluation_model(db, user_id or str(test.user_id))
        )
        resolved = ensure_language_model(source)

    contract = interpret_test_configuration(
        config,
        model=resolved,
        requirement=getattr(test.requirement, "name", None),
        category=getattr(test.category, "name", None),
        topic=getattr(test.topic, "name", None),
    )

    test.test_metadata = store_contract(getattr(test, "test_metadata", None), contract)
    if isinstance(test, Test):
        flag_modified(test, "test_metadata")

    logger.info(
        "Interpreted test %s: adversarial=%s required=%d prohibited=%d confidence=%.2f",
        test.id,
        contract.adversarial,
        len(contract.required_behavior),
        len(contract.prohibited_behavior),
        contract.confidence,
    )
    return contract
