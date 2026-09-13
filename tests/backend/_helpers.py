"""Helpers shared across the backend test suite.

Package-local helpers live next to their tests (``tests/backend/events/_helpers.py``,
``tests/backend/db/utils.py``); this module is for the few that more than one
package needs.
"""

import threading
from typing import Any, Callable


def records_thread(threads: list, result: Any = None) -> Callable[..., Any]:
    """A stand-in that appends the thread it ran on to *threads*, returning *result*.

    Patch it over the synchronous call a coroutine is supposed to have pushed
    into a worker thread, then assert ``threading.get_ident() not in threads``.
    """

    def _call(*_args, **_kwargs):
        threads.append(threading.get_ident())
        return result

    return _call
