"""Jira REST API client for deterministic issue creation."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

import httpx
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.services.tool.rest.config import validate_base_url
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

logger = logging.getLogger(__name__)


class JiraRestClient:
    """Creates Jira issues directly via the Jira REST API v3.

    Uses HTTP Basic Auth (username + API token) against the customer's
    Atlassian cloud instance.
    """

    def __init__(self, base_url: str, username: str, api_token: str):
        validate_base_url(base_url, "JIRA_URL")
        self._base_url = base_url.rstrip("/")
        self._auth = (username, api_token)

    async def health_check(self) -> Dict[str, Any]:
        """Verify credentials and return available projects.

        Calls /rest/api/3/myself for auth and /rest/api/3/project for the
        project list, returned as ``additional_metadata.spaces`` so the
        frontend space selector is populated.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            me_resp = await client.get(f"{self._base_url}/rest/api/3/myself", auth=self._auth)
            if me_resp.status_code != 200:
                return {
                    "is_authenticated": "No",
                    "message": f"Authentication failed: {me_resp.status_code}",
                }

            display = me_resp.json().get("displayName", "")

            projects_resp = await client.get(
                f"{self._base_url}/rest/api/3/project",
                auth=self._auth,
                params={"maxResults": 100},
            )

        spaces: List[Dict[str, str]] = []
        if projects_resp.status_code == 200:
            spaces = [{"key": p["key"], "name": p["name"]} for p in projects_resp.json()]

        result: Dict[str, Any] = {
            "is_authenticated": "Yes",
            "message": f"Connected as {display}",
        }
        if spaces:
            result["additional_metadata"] = {"spaces": spaces}
        return result

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
    ) -> Dict[str, Any]:
        """Create a Jira issue and return its key and URL.

        Args:
            project_key: Jira project key (e.g. "PROJ").
            summary: Issue summary / title.
            description: Optional plain-text description.
            issue_type: Issue type name, defaults to "Task".

        Returns:
            Dict with ``issue_key`` and ``issue_url``.

        Raises:
            ValueError: On authentication failure or API error.
        """
        url = f"{self._base_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description or summary}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, auth=self._auth)

        if resp.status_code == 401:
            raise ValueError("Jira authentication failed. Check your username and API token.")
        if resp.status_code == 403:
            raise ValueError(
                f"Permission denied creating issue in project '{project_key}'. "
                "Ensure the user has the 'Create Issues' permission."
            )
        if resp.status_code == 404:
            raise ValueError(f"Jira project '{project_key}' not found or not accessible.")

        if not resp.is_success:
            error_detail = resp.text[:300]
            raise ValueError(f"Jira API error {resp.status_code}: {error_detail}")

        data = resp.json()
        issue_key = data["key"]
        issue_url = f"{self._base_url}/browse/{issue_key}"
        return {"issue_key": issue_key, "issue_url": issue_url}


async def create_jira_ticket_from_task(
    task_id: uuid.UUID,
    tool_id: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Create a Jira issue from a task via the Jira REST API.

    Returns:
        Dict with ``issue_key`` and ``issue_url``.

    Raises:
        ValueError: If task/tool not found, misconfigured, or the API call fails.
    """
    task = crud.get_task(db, task_id, organization_id, user_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found")

    from rhesis.backend.app.services.tool.rest import config  # avoid circular import

    # Raises ToolConfigurationError if tool xnot found, deleted, or misconfigured.
    client = config.get_rest_client(db, tool_id, organization_id, user_id)
    if not isinstance(client, JiraRestClient):
        raise ValueError(f"Tool '{tool_id}' is not a Jira integration")

    tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    if not tool.tool_metadata or "space_key" not in tool.tool_metadata:
        raise ValueError("Jira tool is not configured with a space_key")

    space_key = tool.tool_metadata["space_key"]

    response_data = await client.create_issue(
        project_key=space_key,
        summary=task.title,
        description=task.description or "",
    )

    if not task.task_metadata:
        task.task_metadata = {}

    task.task_metadata["jira_issue"] = {
        "issue_key": response_data["issue_key"],
        "issue_url": response_data["issue_url"],
        "tool_id": tool_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    crud.update_task(
        db=db,
        task_id=task_id,
        task=schemas.TaskUpdate(task_metadata=task.task_metadata),
        organization_id=organization_id,
        user_id=user_id,
    )

    return {
        **response_data,
        "message": f"Jira ticket {response_data['issue_key']} created successfully",
    }
