"""One writer per batch: finished tests are saved one after another on one session.

Each test used to save on a session of its own, in a thread of its own, so a run held
as many connections as it had tests finishing at once, most of them waiting on the GIL
with a transaction open. The writer holds one connection while it has tests to save.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Tuple

from rhesis.backend.jobs.execution.batch.context import ExecutionContext

logger = logging.getLogger(__name__)

# Saved on one session checkout before it is returned to the pool.
_MAX_GROUP = 50

_Item = Tuple[tuple, "asyncio.Future[None]"]


class ResultWriter:
    """Saves tests with ``persist_result``, in order, on one thread and one session."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self._ctx = ctx
        self._queue: "asyncio.Queue[Optional[_Item]]" = asyncio.Queue()
        self._thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="result-writer")
        self._task = asyncio.ensure_future(self._run())

    async def save(self, *args: Any) -> None:
        """Save one test; returns once it is committed, raises what saving it raised.

        Not cut short by a cancel (revoke or run deadline): the error sweep in
        batch/__init__ would otherwise write a second row for a test being saved.
        """
        done: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        await self._queue.put((args, done))
        try:
            await asyncio.shield(done)
        except asyncio.CancelledError:
            await asyncio.gather(done, return_exceptions=True)
            raise

    async def close(self) -> None:
        """Save what is queued, then stop."""
        await self._queue.put(None)
        await self._task
        self._thread.shutdown(wait=True)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        stopping = False
        while not stopping:
            item = await self._queue.get()
            if item is None:
                return
            group: List[_Item] = [item]
            while len(group) < _MAX_GROUP and not self._queue.empty():
                nxt = self._queue.get_nowait()
                if nxt is None:
                    stopping = True
                    break
                group.append(nxt)
            await loop.run_in_executor(self._thread, self._save_group, loop, group)

    def _save_group(self, loop: asyncio.AbstractEventLoop, group: List[_Item]) -> None:
        """Save each test on one session; release each one as soon as its own row commits."""
        from rhesis.backend.app.database import get_db_with_tenant_variables
        from rhesis.backend.jobs.execution.batch import persist

        ctx = self._ctx
        settled = 0
        try:
            with get_db_with_tenant_variables(
                ctx.organization_id, ctx.user_id or "", ctx.project_id or ""
            ) as db:
                for args, done in group:
                    error: Optional[BaseException] = None
                    try:
                        # persist_result commits or rolls back each test on its own.
                        persist.persist_result(ctx, *args, db=db)
                    except Exception as e:
                        error = e
                    loop.call_soon_threadsafe(_settle, done, error)
                    settled += 1
        except Exception as e:
            logger.error(f"[BATCH] Result writer session failed: {e}", exc_info=True)
            for _, done in group[settled:]:
                loop.call_soon_threadsafe(_settle, done, e)


def _settle(done: "asyncio.Future[None]", error: Optional[BaseException]) -> None:
    if done.done():
        return
    if error is None:
        done.set_result(None)
    else:
        done.set_exception(error)
