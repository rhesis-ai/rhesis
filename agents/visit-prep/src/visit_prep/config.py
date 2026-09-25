"""Per-turn agent configuration, resolved from Rhesis experiment parameters.

A Rhesis experiment can set any of :data:`PARAMETER_NAMES` on the project; everything it leaves
out keeps the value the code ships with. Values come from, in order:

1. the experiment a connector test run was started with (``get_experiment_parameters()``);
2. ``Parameters.get()`` for the project, only when ``RHESIS_PARAMETERS_ENVIRONMENT`` is set, so an
   ordinary run makes no extra API call per turn;
3. the defaults below.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, meta

from rhesis.sdk import Parameters, get_experiment_parameters
from rhesis.sdk.models.parameters import ParameterField, ParameterSchema
from visit_prep.agents.coordinator import COORDINATOR_SYSTEM_PROMPT
from visit_prep.agents.critic import CRITIC_SYSTEM_PROMPT
from visit_prep.agents.history import HISTORY_SYSTEM_PROMPT
from visit_prep.agents.summary import SUMMARY_SYSTEM_PROMPT
from visit_prep.client import default_model

logger = logging.getLogger(__name__)

PROMPT_PARAMETERS: dict[str, str] = {
    "coordinator_prompt": COORDINATOR_SYSTEM_PROMPT,
    "history_prompt": HISTORY_SYSTEM_PROMPT,
    "summary_prompt": SUMMARY_SYSTEM_PROMPT,
    "critic_prompt": CRITIC_SYSTEM_PROMPT,
}
PARAMETER_NAMES: tuple[str, ...] = ("model", "temperature", *PROMPT_PARAMETERS)

_jinja = Environment()


def _template_variables(prompt: str) -> set[str]:
    return meta.find_undeclared_variables(_jinja.parse(prompt))


def _usable_prompt(name: str, prompt: Any) -> bool:
    """Whether ``prompt`` can replace the default ``name`` prompt.

    Haystack turns every template variable into a required Agent input, and the pipeline feeds a
    fixed set of them. A missing or extra ``{{ variable }}`` fails every turn, so require the same
    variables as the default.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    try:
        found = _template_variables(prompt)
    except Exception as exc:
        logger.warning("Experiment %s is not a valid template: %s", name, exc)
        return False
    expected = _template_variables(PROMPT_PARAMETERS[name])
    if found != expected:
        logger.warning(
            "Experiment %s must use exactly these template variables: %s (found: %s)",
            name,
            sorted(expected) or "none",
            sorted(found) or "none",
        )
        return False
    return True


@dataclass(frozen=True)
class VisitPrepConfig:
    """Everything an experiment can vary. Frozen so it can key the pipeline cache."""

    model: str = field(default_factory=default_model)
    temperature: float | None = None
    coordinator_prompt: str = COORDINATOR_SYSTEM_PROMPT
    history_prompt: str = HISTORY_SYSTEM_PROMPT
    summary_prompt: str = SUMMARY_SYSTEM_PROMPT
    critic_prompt: str = CRITIC_SYSTEM_PROMPT

    @classmethod
    def from_parameters(cls, params: Mapping[str, Any] | None) -> VisitPrepConfig:
        """Build a config from resolved parameter values, ignoring unknown or unusable ones."""
        if not params:
            return cls()
        overrides: dict[str, Any] = {}
        model = params.get("model")
        if isinstance(model, str) and model.strip():
            overrides["model"] = model.strip()
        temperature = params.get("temperature")
        # bool is an int subclass; a boolean slot named "temperature" is a schema mistake.
        if isinstance(temperature, int | float) and not isinstance(temperature, bool):
            overrides["temperature"] = float(temperature)
        for name in PROMPT_PARAMETERS:
            prompt = params.get(name)
            if _usable_prompt(name, prompt):
                overrides[name] = prompt
        ignored = set(params) - set(overrides)
        if ignored:
            logger.warning("Ignoring experiment parameters: %s", ", ".join(sorted(ignored)))
        return cls(**overrides)


def resolve_config() -> VisitPrepConfig:
    """Return the config for the current turn. Never raises: a lookup failure means defaults."""
    params = get_experiment_parameters()
    if params is None and os.getenv("RHESIS_PARAMETERS_ENVIRONMENT"):
        project_id = os.getenv("RHESIS_PROJECT_ID")
        try:
            # Parameters.get reads the environment from RHESIS_PARAMETERS_ENVIRONMENT itself
            # and caches the answer for 60 s.
            params = Parameters.get(project_id=project_id)
        except Exception as exc:
            logger.warning("Could not resolve Rhesis parameters; using defaults: %s", exc)
    return VisitPrepConfig.from_parameters(params)


def parameter_schema() -> ParameterSchema:
    """The schema matching :class:`VisitPrepConfig`, with today's values as defaults."""
    defaults = VisitPrepConfig()
    fields = [
        ParameterField(
            name="model",
            type="string",
            description="Gemini model id used by every agent.",
            default=defaults.model,
            display_order=0,
        ),
        ParameterField(
            name="temperature",
            type="number",
            description="Sampling temperature for every agent. Unset means Gemini's default.",
            display_order=1,
        ),
    ]
    for order, (name, prompt) in enumerate(PROMPT_PARAMETERS.items(), start=2):
        description = f"System prompt for the {name.removesuffix('_prompt')} agent."
        variables = sorted(_template_variables(prompt))
        if variables:
            kept = ", ".join(f"{{{{ {v} }}}}" for v in variables)
            description += f" Must keep {kept} and add no other template variables."
        fields.append(
            ParameterField(
                name=name,
                type="text",
                description=description,
                default=prompt,
                display_order=order,
            )
        )
    return ParameterSchema(fields=fields)


__all__ = [
    "PARAMETER_NAMES",
    "PROMPT_PARAMETERS",
    "VisitPrepConfig",
    "parameter_schema",
    "resolve_config",
]
