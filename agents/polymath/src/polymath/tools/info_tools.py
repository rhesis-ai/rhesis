"""HTTP tools for the Info Specialist agent.

These tools deliberately make real network calls so each invocation produces a
non-trivial ``ai.tool.invoke`` span (with ``ai.tool.input`` / ``ai.tool.output``
events) for the Rhesis SDK's MAF translator to ingest.

Both endpoints are public, key-free APIs:

* ``get_current_time`` -> https://worldtimeapi.org
* ``wikipedia_summary`` -> https://en.wikipedia.org/api/rest_v1/page/summary
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote

import requests
from agent_framework import tool
from pydantic import Field

_HTTP_TIMEOUT_SECONDS: float = 10.0
_USER_AGENT: str = "polymath-maf-demo/0.1 (+https://rhesis.ai)"


@tool
def get_current_time(
    timezone: Annotated[
        str,
        Field(
            description=(
                "IANA timezone name, e.g. 'UTC', 'Europe/Berlin', 'Asia/Tokyo', "
                "'America/Los_Angeles'."
            ),
        ),
    ] = "UTC",
) -> dict[str, Any]:
    """Return the current time in the given IANA timezone.

    Wraps the public worldtimeapi.org service; the response includes
    ``datetime``, ``timezone``, ``utc_offset``, and ``day_of_week``.
    """
    url = f"https://worldtimeapi.org/api/timezone/{quote(timezone, safe='/')}"
    response = requests.get(
        url,
        timeout=_HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()
    # Trim to the most useful fields so the tool span event stays compact.
    return {
        "timezone": payload.get("timezone"),
        "datetime": payload.get("datetime"),
        "utc_offset": payload.get("utc_offset"),
        "day_of_week": payload.get("day_of_week"),
        "abbreviation": payload.get("abbreviation"),
    }


@tool
def wikipedia_summary(
    topic: Annotated[
        str,
        Field(description="The topic to look up on the English Wikipedia."),
    ],
) -> dict[str, Any]:
    """Return a one-paragraph English Wikipedia summary for ``topic``.

    Uses the public Wikipedia REST `page/summary` endpoint. No API key
    required.
    """
    url = (
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        f"{quote(topic.replace(' ', '_'), safe='')}"
    )
    response = requests.get(
        url,
        timeout=_HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "title": payload.get("title"),
        "description": payload.get("description"),
        "extract": payload.get("extract"),
        "url": (payload.get("content_urls") or {}).get("desktop", {}).get("page"),
    }


INFO_TOOLS = [get_current_time, wikipedia_summary]
