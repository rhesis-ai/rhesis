"""MCP Extract Agent for extracting full content from specific pages."""

import json
import logging
from typing import Any, Dict, List, Optional

from rhesis.sdk.services.mcp.agents.base_agent import BaseMCPAgent
from rhesis.sdk.services.mcp.schemas import (
    ExecutionStep,
    ExtractedPage,
    ExtractionResult,
    PageMetadata,
)

logger = logging.getLogger(__name__)


class MCPExtractAgent(BaseMCPAgent):
    """
    Specialized agent for extracting full content from known pages.

    Given page IDs (from search results or direct input), fetches complete content
    including metadata, converting it to markdown format. Works with any MCP server.
    """

    EXTRACT_SYSTEM_PROMPT = """You are a content extraction agent.

Your task: Extract full content from specified pages/documents/files.

IMPORTANT: Return results in this exact JSON format:
{
  "pages": [
    {
      "page_id": "the page ID provided",
      "title": "page title or 'Untitled' if missing",
      "content": "full extracted content as markdown or plain text",
      "metadata": {
        "page_id": "...",
        "title": "page title or 'Untitled' if missing",
        "url": "...",
        "last_edited": "...",
        "created_at": "...",
        "excerpt": "...",
        "author": "...",
        "source_type": "notion/github/etc",
        "raw_metadata": {}
      },
      "source_type": "notion/github/slack/etc"
    }
  ]
}

CRITICAL: When creating the JSON response:
- Ensure all strings in the "content" field have proper JSON escaping
- Replace literal newlines with \\n
- Replace literal tabs with \\t
- Escape quotes properly
- The JSON must be valid and parseable

Workflow:
1. For each page_id provided, use tools to fetch full content
   - Notion: Use API-retrieve-a-page for metadata, then API-get-block-children for content
   - GitHub: Use get_file_contents or similar
   - Slack: Use get_thread_messages or similar
2. Extract metadata (title, URL, timestamps, author)
3. If a page has no title, use "Untitled" as the title value
4. Format content as readable markdown or plain text
5. Return using action="finish" with the JSON containing all extracted pages

Make content readable: Convert blocks/formatting to markdown where possible.
Include ALL content from the page, not just excerpts.
If title is missing or null, always use "Untitled" as the fallback."""

    def __init__(
        self,
        llm,
        mcp_client,
        max_iterations: int = 15,
        verbose: bool = False,
        stop_on_error: bool = True,
        provider_config=None,
    ):
        super().__init__(
            llm,
            mcp_client,
            max_iterations,
            verbose,
            stop_on_error,
            provider_config=provider_config,
        )

    def get_system_prompt(self) -> str:
        return self.EXTRACT_SYSTEM_PROMPT

    def get_agent_name(self) -> str:
        return "📄 MCP Extract Agent"

    def build_prompt(
        self, task_input: Any, available_tools: List[Dict[str, Any]], history: List[ExecutionStep]
    ) -> str:
        # task_input is dict with 'page_ids' and optional 'context'
        if isinstance(task_input, dict):
            page_ids = task_input.get("page_ids", [])
            context = task_input.get("context")
        else:
            page_ids = task_input
            context = None

        tools_text = self._format_tools(available_tools)
        history_text = self._format_history(history, max_len=5000)

        context_str = json.dumps(context) if context else "None"
        prompt = f"""Extract content from these page IDs: {page_ids}
Context: {context_str}

Available MCP Tools:
{tools_text}

"""
        if history_text:
            prompt += f"""Execution History:
{history_text}

Based on the page IDs, available tools, and execution history above, decide what to do next.

"""
        else:
            prompt += """This is the first iteration. Extract full content \
from all specified pages.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking
- action: Either "call_tool" (to fetch content) or "finish" (when you have \
all content)
- tool_calls: List of tools to call if action="call_tool"
- final_answer: JSON with extracted pages if action="finish"

Then, return the pages with full content in the JSON format specified in the \
system prompt."""

        return prompt

    def parse_result(self, final_answer: str, history: List[ExecutionStep]) -> ExtractionResult:
        """Parse LLM's JSON response into ExtractionResult with full page content."""
        pages = self._parse_pages(final_answer)

        return ExtractionResult(
            pages=pages,
            total_extracted=len(pages),
            execution_history=history,
            iterations_used=len(history),
            success=True,
        )

    def create_error_result(
        self, error: str, history: List[ExecutionStep], iterations: int
    ) -> ExtractionResult:
        return ExtractionResult(
            pages=[],
            total_extracted=0,
            execution_history=history,
            iterations_used=iterations,
            success=False,
            error=error,
        )

    def _parse_pages(self, final_answer: str) -> List[ExtractedPage]:
        """
        Parse LLM's JSON response into ExtractedPage objects with full content.

        Includes fallback recovery for malformed JSON responses.
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
                    # Ensure metadata is a PageMetadata object
                    if "metadata" in page_data and isinstance(page_data["metadata"], dict):
                        page_data["metadata"] = PageMetadata(**page_data["metadata"])

                    page = ExtractedPage(**page_data)
                    pages.append(page)
                except Exception as e:
                    logger.warning(f"Failed to parse extracted page: {e}")
                    continue

            return pages

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction results as JSON: {e}")
            logger.debug(f"Raw final_answer (first 500 chars): {final_answer[:500]}")

            # Try to extract what we can from the malformed response
            # This is a fallback for when the LLM doesn't properly escape JSON
            try:
                # Attempt to fix common JSON issues
                import re

                # Try to find JSON-like structure in the response
                json_match = re.search(r"\{[\s\S]*\}", final_answer)
                if json_match:
                    potential_json = json_match.group(0)
                    # Try parsing the extracted portion
                    data = json.loads(potential_json)
                    if isinstance(data, dict) and "pages" in data:
                        logger.info("Successfully recovered from malformed JSON")
                        return self._parse_pages(json.dumps(data))
            except Exception:
                pass

            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing extraction results: {e}")
            return []

    async def run_async(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract full content from specified pages.

        Args:
            page_ids: List of page IDs to extract (from search results or known IDs)
            context: Optional context for guiding extraction (purpose, query, etc.)

        Returns:
            ExtractionResult with full content for each page
        """
        task_input = {"page_ids": page_ids, "context": context}
        return await super().run_async(task_input)

    def run(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """Synchronous wrapper for run_async."""
        task_input = {"page_ids": page_ids, "context": context}
        return super().run(task_input)
