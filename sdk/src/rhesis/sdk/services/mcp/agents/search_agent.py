"""MCP Search Agent for finding and listing pages from any MCP server."""

import json
import logging
from typing import Any, Dict, List

from rhesis.sdk.services.mcp.agents.base_agent import BaseMCPAgent
from rhesis.sdk.services.mcp.schemas import ExecutionStep, PageMetadata, SearchResult

logger = logging.getLogger(__name__)


class MCPSearchAgent(BaseMCPAgent):
    """
    Specialized agent for searching and discovering pages/documents/files.

    Uses MCP tools (like Notion's search API or GitHub's repository search) to
    find content matching a query. Returns structured PageMetadata for each result.
    """

    SEARCH_SYSTEM_PROMPT = """You are a search agent that finds pages/documents/files.

Your task: Use available MCP tools to search for pages matching the user's query.

CRITICAL RULES:
- ONLY return pages that were ACTUALLY returned by the MCP tools
- DO NOT invent, guess, or hallucinate page IDs or content
- If no results are found, return an empty pages array
- Extract data ONLY from the actual tool responses

IMPORTANT: Return results in this exact JSON format:
{
  "pages": [
    {
      "page_id": "unique ID from the service (MUST be from actual tool results)",
      "title": "page/file title or 'Untitled' if missing",
      "url": "direct link to the page (check 'url' field in API response)",
      "last_edited": "ISO timestamp if available or null",
      "created_at": "ISO timestamp if available or null",
      "excerpt": "brief content preview (1-2 sentences) or null",
      "author": "author/creator name if available or null",
      "source_type": "notion/github/slack/etc",
      "raw_metadata": {"complete original API response object"}
    }
  ]
}

Workflow:
1. Search using available tools (e.g., API-post-search for Notion, search_repositories for GitHub)
2. For EACH result ACTUALLY returned by the tool, extract the fields above
3. Extract URL from the API response (Notion pages have a 'url' field, GitHub has 'html_url')
4. Store the COMPLETE original result object in raw_metadata
5. If a page has no title, use "Untitled" as the title value
6. Return using action="finish" with ONLY the pages that were in the tool results

CRITICAL: Extract the 'url' field from each page in the API response!
For Notion: Look for page.url in the results
For GitHub: Look for html_url or url in the results

VALIDATION: Every page_id you return MUST have appeared in a tool result. Do not make up IDs."""

    def get_system_prompt(self) -> str:
        return self.SEARCH_SYSTEM_PROMPT

    def get_agent_name(self) -> str:
        return "🔍 MCP Search Agent"

    def build_prompt(
        self, task_input: Any, available_tools: List[Dict[str, Any]], history: List[ExecutionStep]
    ) -> str:
        query = str(task_input)
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history(history, max_len=5000)

        prompt = f"""Search Query: {query}

Available MCP Tools:
{tools_text}

"""
        if history_text:
            prompt += f"""Execution History:
{history_text}

Based on the query, available tools, and execution history above, decide what to do next.

"""
        else:
            prompt += """This is the first iteration. Search for pages matching the query.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking
- action: Either "call_tool" (to search) or "finish" (when you have results)
- tool_calls: List of tools to call if action="call_tool"
- final_answer: JSON with pages list if action="finish"

When finishing, return the pages in the exact JSON format specified in the system prompt."""

        return prompt

    def parse_result(self, final_answer: str, history: List[ExecutionStep]) -> SearchResult:
        """Parse LLM's JSON response into SearchResult with list of PageMetadata."""
        pages = self._parse_pages(final_answer)

        # Extract query from history
        query = "Unknown query"
        if history:
            query = history[0].reasoning[:100]

        return SearchResult(
            pages=pages,
            total_found=len(pages),
            query=query,
            execution_history=history,
            iterations_used=len(history),
            success=len(pages) > 0,
            error=(None if len(pages) > 0 else "No valid pages found in search results"),
        )

    def create_error_result(
        self, error: str, history: List[ExecutionStep], iterations: int
    ) -> SearchResult:
        return SearchResult(
            pages=[],
            total_found=0,
            query="",
            execution_history=history,
            iterations_used=iterations,
            success=False,
            error=error,
        )

    def _parse_pages(self, final_answer: str) -> List[PageMetadata]:
        """
        Parse LLM's JSON response into PageMetadata objects.

        Handles both {"pages": [...]} and direct array formats.
        """
        try:
            data = json.loads(final_answer)

            if isinstance(data, dict) and "pages" in data:
                pages_data = data["pages"]
            elif isinstance(data, list):
                pages_data = data
            else:
                logger.warning(f"Unexpected data format: {type(data)}")
                return []

            pages = []
            for page_data in pages_data:
                try:
                    page = PageMetadata(**page_data)
                    pages.append(page)
                except Exception as e:
                    logger.warning(f"Failed to parse page metadata: {e}")
                    continue

            return pages

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse search results as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing search results: {e}")
            return []

    async def run_async(self, query: str) -> SearchResult:
        """
        Search for pages matching the query.

        Args:
            query: Natural language search query (e.g., "Find PRD documents")

        Returns:
            SearchResult with list of matching pages
        """
        return await super().run_async(query)

    def run(self, query: str) -> SearchResult:
        """Synchronous wrapper for run_async."""
        return super().run(query)
