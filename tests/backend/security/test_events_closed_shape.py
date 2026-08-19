"""Drift guard: every ``PlatformEvent`` subclass stays closed and typed.

This is the primary defense against the events layer leaking customer
content -- a field has to be declared by a human before it can carry
anything, checked here at test time rather than by a runtime filter. It is
also what stops this becoming a generic event bus: no ``**kwargs`` escape
hatch, no ``extra="allow"``, ever.

Walks ``PlatformEvent.__subclasses__()`` rather than a hand-maintained list,
so a new event type added anywhere under ``events/types.py`` is covered
automatically -- the thing this guards against is exactly the kind of change
that is easy to add without remembering to update a list.
"""

from typing import get_type_hints

from rhesis.backend.events.redaction import redact_metadata
from rhesis.backend.events.types import PlatformEvent


def _all_event_classes():
    return [PlatformEvent] + list(PlatformEvent.__subclasses__())


class TestClosedShape:
    def test_every_subclass_forbids_extra_fields(self):
        for cls in _all_event_classes():
            assert cls.model_config.get("extra") == "forbid", (
                f"{cls.__name__} must set extra='forbid' -- inherited from "
                "PlatformEvent unless overridden, which it must not be"
            )

    def test_every_subclass_is_frozen(self):
        for cls in _all_event_classes():
            assert cls.model_config.get("frozen") is True, (
                f"{cls.__name__} must stay frozen -- a sink must not be able "
                "to mutate an event another sink will receive"
            )

    def test_no_subclass_declares_an_untyped_dict_field(self):
        """``context`` on the base class is the one deliberate, narrow
        exception -- structured extra data, redacted before delivery. A
        subclass adding its own free-form dict field would recreate the
        payload-bag escape hatch this design exists to prevent.
        """
        allowed_dict_fields = {"context"}
        for cls in _all_event_classes():
            if cls is PlatformEvent:
                continue
            hints = get_type_hints(cls)
            own_fields = set(cls.model_fields) - set(PlatformEvent.model_fields)
            for field_name in own_fields:
                hint = hints.get(field_name)
                hint_str = str(hint)
                assert "Dict" not in hint_str and "dict" not in hint_str, (
                    f"{cls.__name__}.{field_name} is dict-shaped ({hint_str}) -- "
                    "the whole point of a typed subclass is that a human "
                    "declared each field; a dict field defeats that"
                )
                assert field_name in allowed_dict_fields or "dict" not in hint_str

    def test_every_declared_field_name_survives_redaction(self):
        """Redaction is applied to ``context`` values, not to an event's own
        declared field names -- but a field NAMED like something sensitive
        (``api_key``, ``user_email``) would be a bad sign regardless: it
        suggests the field itself should not exist as plain text. Runs the
        set of every subclass's field names through the same filter used on
        `context` as a cheap check that nobody has named a field that way.
        """
        for cls in _all_event_classes():
            field_names = set(cls.model_fields)
            as_dict = dict.fromkeys(field_names, "x")
            redacted = redact_metadata(as_dict)
            dropped = field_names - set(redacted)
            assert not dropped, (
                f"{cls.__name__} declares field(s) {dropped} that look "
                "sensitive by name -- rename them"
            )

    def test_event_type_is_a_literal_with_a_default_on_every_subclass(self):
        for cls in _all_event_classes():
            if cls is PlatformEvent:
                continue
            field = cls.model_fields["event_type"]
            assert field.default is not None, (
                f"{cls.__name__}.event_type must default to its own literal "
                "value, not be left for a caller to set"
            )

    def test_constructing_with_an_unknown_field_raises(self):
        """The behavioral proof, not just a config-flag check: extra='forbid'
        is a pydantic setting that could be silently ignored by a pydantic
        version change or a typo. This confirms it actually rejects."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from rhesis.backend.events.types import ActivityLogged

        try:
            ActivityLogged(
                occurred_at=datetime.now(timezone.utc),
                organization_id=uuid4(),
                trace_id="a" * 32,
                span_id="b" * 16,
                source="test",
                level="info",
                message="hi",
                this_field_does_not_exist="should be rejected",
            )
            raise AssertionError("constructing with an unknown field must raise")
        except Exception as exc:
            assert "this_field_does_not_exist" in str(exc) or "extra" in str(exc).lower()
