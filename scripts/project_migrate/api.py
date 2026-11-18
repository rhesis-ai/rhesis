"""HTTP access to one Rhesis instance: one request at a time, paced, with backoff.

A POST is never retried blind. When its outcome is unclear the caller gets AmbiguousWrite and
must look the record up before trying again.
"""

from __future__ import annotations

import http.client
import json
import random
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

USER_AGENT = "rhesis-project-migrate/1.0"
PAGE = 100  # list routes reject a larger limit
MAX_ATTEMPTS = 6
TIMEOUT_SECONDS = 60.0


class Abort(Exception):
    """Stop the run. State is already saved, so apply can resume."""


class AmbiguousWrite(Exception):
    """A write was sent but we don't know whether the server applied it."""


class ConnectFailed(Exception):
    """The request never reached the server, so any method is safe to retry."""


class SendFailed(Exception):
    """The connection broke after the request may have been sent."""


@dataclass
class Response:
    status: int
    headers: dict[str, str]  # names lowercased
    body: bytes


class Transport(Protocol):
    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
    ) -> Response: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def urllib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
) -> Response:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, _lower_keys(r.headers), r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, _lower_keys(e.headers or {}), e.read())
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.gaierror, ConnectionRefusedError)):
            raise ConnectFailed(repr(e.reason)) from e
        raise SendFailed(repr(e.reason)) from e
    except (TimeoutError, ConnectionError, http.client.HTTPException) as e:
        raise SendFailed(repr(e)) from e


def _lower_keys(headers) -> dict[str, str]:
    # Servers send header names in any case (uvicorn sends lowercase); compare them lowercased.
    return {k.lower(): v for k, v in headers.items()}


def stderr_log(msg: str) -> None:
    print(msg, file=sys.stderr)


class Api:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        project_id: str,
        *,
        read_rps: float = 5.0,
        write_rps: float = 2.0,
        label: str = "api",
        transport: Transport = urllib_transport,
        clock: Clock | None = None,
        log: Callable[[str], None] = stderr_log,
    ):
        self.base = base_url.rstrip("/")
        self.project_id = project_id
        self.label = label
        self.transport = transport
        self.clock = clock or RealClock()
        self.log = log
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            # Some proxies reject Python's default User-Agent, so send our own.
            "User-Agent": USER_AGENT,
            "X-Project-Id": project_id,
            "Accept": "application/json",
        }
        self.min_gap = {"read": 1.0 / read_rps, "write": 1.0 / write_rps}
        self.last = {"read": float("-inf"), "write": float("-inf")}
        self.calls = {"read": 0, "write": 0}

    def _pace(self, kind: str) -> None:
        wait = self.last[kind] + self.min_gap[kind] - self.clock.monotonic()
        if wait > 0:
            self.clock.sleep(wait)
        self.last[kind] = self.clock.monotonic()

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        if retry_after:
            try:
                self.clock.sleep(min(float(retry_after), 120.0))
                return
            except ValueError:
                pass
        self.clock.sleep(min(60.0, 2 ** (attempt - 1)) + random.uniform(0, 0.5))

    def request(
        self, method: str, path: str, *, params: dict | None = None, body: Any = None
    ) -> Any:
        kind = "read" if method == "GET" else "write"
        # PUT, PATCH and DELETE are idempotent. POST is not.
        blind_retry_ok = method in ("GET", "PUT", "PATCH", "DELETE")
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = dict(self.headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._pace(kind)
            self.calls[kind] += 1
            try:
                r = self.transport(method, url, headers, data, TIMEOUT_SECONDS)
            except ConnectFailed as e:
                self.log(f"  [{self.label}] connect error ({e}), retry {attempt}")
                self._backoff(attempt)
                continue
            except SendFailed as e:
                if not blind_retry_ok:
                    raise AmbiguousWrite(f"{method} {path}: {e}") from e
                self.log(f"  [{self.label}] connection broke ({e}), retry {attempt}")
                self._backoff(attempt)
                continue

            if r.status == 429:
                # A rate-limited request was not processed, so every method can retry.
                self.log(f"  [{self.label}] 429, backing off")
                self._backoff(attempt, r.headers.get("retry-after"))
                continue
            if r.status >= 500:
                # A failed POST may still have been saved, so the caller looks before retrying.
                if not blind_retry_ok:
                    raise AmbiguousWrite(f"{method} {path}: HTTP {r.status}")
                self.log(f"  [{self.label}] HTTP {r.status}, retry {attempt}")
                self._backoff(attempt)
                continue
            if r.status >= 400:
                raise HttpError(self.label, method, path, params, body, r)
            return json.loads(r.body) if r.body else None
        raise Abort(f"[{self.label}] {method} {path}: gave up after {MAX_ATTEMPTS} attempts")

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params or None)

    def get_all(self, path: str, *, until_empty: bool = False, **params: Any) -> list[dict]:
        """Every page of a list route.

        `until_empty` is for routes that drop rows after paging (the experiments list hides
        other users' private ones), where a short page doesn't mean the last page.
        """
        out: list[dict] = []
        skip = 0
        while True:
            page = self.get(
                path, limit=PAGE, skip=skip, sort_by="created_at", sort_order="asc", **params
            )
            out.extend(page)
            if not page or (len(page) < PAGE and not until_empty):
                return out
            skip += PAGE

    def project_filter(self) -> dict:
        return {"$filter": f"project_id eq {odata_str(self.project_id)}"}


class HttpError(Abort):
    """A 4xx other than 429. Retrying won't change the answer."""

    def __init__(
        self, label: str, method: str, path: str, params: Any, body: Any, r: Response
    ) -> None:
        self.status = r.status
        try:
            self.body = json.loads(r.body)
        except ValueError:
            self.body = None
        super().__init__(
            f"[{label}] {method} {path} -> HTTP {r.status}\n"
            f"  params={params}\n  body={json.dumps(body, default=str)[:2000]}\n"
            f"  response={r.body[:2000].decode(errors='replace')}"
        )


def odata_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"
