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
    """Agent for extracting full content from specific pages."""

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
            debug=False,
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
        """Parse the LLM's final answer into ExtractedPage objects."""
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
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing extraction results: {e}")
            return []

    # Keep backward compatibility
    async def run_async(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        task_input = {"page_ids": page_ids, "context": context}
        return await super().run_async(task_input)

    def run(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        task_input = {"page_ids": page_ids, "context": context}
        return super().run(task_input)
