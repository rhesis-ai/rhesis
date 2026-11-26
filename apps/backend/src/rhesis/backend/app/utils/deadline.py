"""Wall-clock limits that a job enforces on itself.

Celery's time limits are inert on the thread pool, so a job that may run long checks a
:class:`Deadline` at its own loop points and stops with :class:`JobTimeLimitExceeded`.
"""

import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional


class JobTimeLimitExceeded(Exception):
    """A job stopped itself at its wall-clock limit; a retry would only hit it again."""


class _DeadlineReached(BaseException):
    # A BaseException, like asyncio.CancelledError, so library code that catches
    # Exception (the SDK synthesizers do) lets it through. Never leaves enforced().
    pass


class Deadline:
    """A point in time *seconds* from now, after which *what* must stop."""

    def __init__(self, seconds: float, what: str):
        self.seconds = seconds
        self.what = what
        self._at = time.monotonic() + seconds

    def expired(self) -> bool:
        return time.monotonic() >= self._at

    def _error(self) -> JobTimeLimitExceeded:
        return JobTimeLimitExceeded(f"{self.what} stopped after {self.seconds:g}s")

    def check(self) -> None:
        """Raise :class:`JobTimeLimitExceeded` once the deadline has passed."""
        if self.expired():
            raise self._error()

    def guard(
        self, callback: Optional[Callable[[int, int], None]] = None
    ) -> Callable[[int, int], None]:
        """A progress callback that stops the caller once the deadline has passed.

        For code that reports progress but catches ``Exception`` around it. Use it
        inside :meth:`enforced`, which turns the stop into ``JobTimeLimitExceeded``.
        """

        def checked(current: int, total: int) -> None:
            if callback:
                callback(current, total)
            if self.expired():
                raise _DeadlineReached()

        return checked

    @contextmanager
    def enforced(self) -> Iterator["Deadline"]:
        """Raise ``JobTimeLimitExceeded`` for a stop raised by :meth:`guard` inside."""
        try:
            yield self
        except _DeadlineReached:
            raise self._error() from None
