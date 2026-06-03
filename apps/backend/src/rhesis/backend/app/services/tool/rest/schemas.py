"""Shared data types for REST source implementations."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchedSource:
    """A single source fetched from an external tool.

    Returned by NotionRestClient.fetch_all() and GitHubRestClient.fetch_all().
    """

    id: str
    title: str
    content: str
    url: Optional[str] = None
