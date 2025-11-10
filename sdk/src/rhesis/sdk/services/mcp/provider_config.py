"""Provider-specific configurations for MCP response filtering."""

import copy
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """
    Configuration for filtering verbose MCP API responses.

    Some MCP servers (like Notion) return very large responses with nested objects.
    This config extracts only essential fields to reduce token usage and improve
    LLM reasoning efficiency.

    Example: Notion search might return 50KB per page. Filtering reduces it to 2KB.
    """

    name: str
    search_tools: List[str] = field(default_factory=list)
    essential_fields: Dict[str, List[str]] = field(default_factory=dict)

    def should_filter(self, tool_name: str) -> bool:
        """Check if a tool should have its response filtered."""
        return tool_name in self.search_tools and tool_name in self.essential_fields

    def get_essential_fields(self, tool_name: str) -> List[str]:
        """Get the list of essential fields for a specific tool."""
        return self.essential_fields.get(tool_name, [])

    def filter_response(self, result: Any, tool_name: str) -> Any:
        """
        Filter verbose API responses to essential fields only.

        Args:
            result: Raw MCP tool result with potentially large nested objects
            tool_name: Name of the tool that was called

        Returns:
            Filtered result with only essential fields, or original if no filter defined
        """
        if not self.should_filter(tool_name):
            return result

        # Get essential fields for this tool
        essential_fields = self.get_essential_fields(tool_name)
        if not essential_fields:
            return result

        try:
            # Extract content from result
            content_list = getattr(result, "content", None)
            if not content_list:
                return result

            # Filter each content item
            filtered_content = []
            for content_item in content_list:
                if hasattr(content_item, "text"):
                    try:
                        # Parse JSON response
                        data = json.loads(content_item.text)

                        # Filter the data
                        filtered_data = self._filter_json_data(data, essential_fields)

                        # Create new content item with filtered data
                        # We need to preserve the content item structure
                        # but replace the text with filtered JSON
                        filtered_item = copy.copy(content_item)
                        filtered_item.text = json.dumps(filtered_data)
                        filtered_content.append(filtered_item)

                    except json.JSONDecodeError:
                        # Not JSON, keep as is
                        filtered_content.append(content_item)
                else:
                    # No text attribute, keep as is
                    filtered_content.append(content_item)

            # Replace content in result
            result.content = filtered_content
            return result

        except Exception as e:
            logger.warning(f"Failed to filter response for {tool_name}: {e}")
            # Return original result if filtering fails
            return result

    def _filter_json_data(self, data: Any, essential_fields: List[str]) -> Any:
        """
        Recursively filter JSON data to include only essential fields.

        Args:
            data: JSON data (dict, list, or primitive)
            essential_fields: List of field paths to keep (supports dot notation)

        Returns:
            Filtered data structure
        """
        if isinstance(data, dict):
            # Check if this is a results wrapper (common in search APIs)
            if "results" in data and isinstance(data["results"], list):
                # Filter each item in results array
                filtered_results = [
                    self._extract_essential_fields(item, essential_fields)
                    for item in data["results"]
                ]
                return {
                    "results": filtered_results,
                    "has_more": data.get("has_more"),
                    "next_cursor": data.get("next_cursor"),
                }
            else:
                # Single item, filter it
                return self._extract_essential_fields(data, essential_fields)

        elif isinstance(data, list):
            # List of items, filter each
            return [self._extract_essential_fields(item, essential_fields) for item in data]

        else:
            # Primitive value, return as is
            return data

    def _extract_essential_fields(
        self, item: Dict[str, Any], essential_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Extract only essential fields from a dictionary.

        Supports dot notation for nested fields (e.g., "properties.Name").

        Args:
            item: Dictionary to filter
            essential_fields: List of field paths to extract

        Returns:
            Dictionary with only essential fields
        """
        if not isinstance(item, dict):
            return item

        filtered = {}

        for field_path in essential_fields:
            # Handle dot notation for nested fields
            if "." in field_path:
                parts = field_path.split(".")
                value = item
                found = True

                # Navigate to nested value
                for part in parts[:-1]:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        found = False
                        break

                # Extract final value
                if found and isinstance(value, dict) and parts[-1] in value:
                    # Create nested structure in filtered dict
                    current = filtered
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = value[parts[-1]]

            else:
                # Simple field
                if field_path in item:
                    filtered[field_path] = item[field_path]

        return filtered


# Notion Provider Configuration
NOTION_CONFIG = ProviderConfig(
    name="notion",
    search_tools=[
        "API-post-search",
        "API-post-database-query",
    ],
    essential_fields={
        "API-post-search": [
            "id",
            "object",
            "url",
            "last_edited_time",
            "created_time",
            "properties.Name",  # Nested field using dot notation
            "parent",
        ],
        "API-post-database-query": [
            "id",
            "object",
            "url",
            "last_edited_time",
            "created_time",
            "properties.Name",
            "parent",
        ],
    },
)

# GitHub Provider Configuration (example for future use)
GITHUB_CONFIG = ProviderConfig(
    name="github",
    search_tools=[
        "search_repositories",
        "search_issues",
        "search_code",
    ],
    essential_fields={
        "search_repositories": [
            "id",
            "name",
            "full_name",
            "html_url",
            "description",
            "updated_at",
            "stargazers_count",
        ],
        "search_issues": [
            "id",
            "number",
            "title",
            "html_url",
            "state",
            "created_at",
            "updated_at",
            "user.login",
        ],
        "search_code": [
            "name",
            "path",
            "html_url",
            "repository.full_name",
        ],
    },
)

# Slack Provider Configuration (example for future use)
SLACK_CONFIG = ProviderConfig(
    name="slack",
    search_tools=[
        "search_messages",
        "search_files",
    ],
    essential_fields={
        "search_messages": [
            "ts",
            "text",
            "user",
            "channel",
            "permalink",
        ],
        "search_files": [
            "id",
            "name",
            "title",
            "url_private",
            "timestamp",
            "user",
        ],
    },
)
