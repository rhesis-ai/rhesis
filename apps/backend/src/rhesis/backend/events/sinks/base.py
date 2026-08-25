"""The protocol every event sink implements.

Adding a sink should touch only: a new module here, one ``register_sink(...)``
call, and (for a sink with its own storage) a table and migration. If adding
one required touching emit call sites, the dispatcher design would be wrong.
"""

from typing import Optional, Protocol

from sqlalchemy.orm import Session

from rhesis.backend.events.types import PlatformEvent


class Sink(Protocol):
    """A delivery target for platform events.

    ``critical`` decides what a failure means, in the dispatcher: a
    non-critical sink's exception is logged and swallowed, so a dropped log
    line never fails the work it was describing. A critical sink's exception
    propagates -- a compliance record that silently failed to write is worse
    than a failed request.
    """

    name: str
    critical: bool

    def handles(self, event: PlatformEvent) -> bool:
        """Whether this sink acts on this event type. Checked before delivery
        so a sink with nothing to do for an event type is never called."""
        ...

    def deliver(self, event: PlatformEvent, db: Optional[Session]) -> None:
        """Write the event. Raise on failure -- the dispatcher decides what
        that means from ``critical``, not this method."""
        ...
