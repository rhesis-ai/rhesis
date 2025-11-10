"""MCP Extract Agent for extracting full content from specific pages."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    ExecutionStep,
    ExtractedPage,
    ExtractionResult,
    PageMetadata,
    ToolResult,
)

logger = logging.getLogger(__name__)


class MCPExtractAgent:
    """
    Agent for extracting full content from specific pages.

    This agent uses LLM-based normalization to transform diverse service responses
    into a unified ExtractedPage schema with full content.
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
        llm: BaseLLM,
        mcp_client: MCPClient,
        max_iterations: int = 15,
        verbose: bool = False,
        stop_on_error: bool = True,
    ):
        """
        Initialize the MCP Extract Agent.

        Args:
            llm: An instance of BaseLLM
            mcp_client: MCP client instance
            max_iterations: Maximum number of ReAct iterations (default: 15)
            verbose: If True, prints detailed execution information
            stop_on_error: If True, raises exception on errors (default: True)
        """
        self.llm = llm
        self.mcp_client = mcp_client
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.stop_on_error = stop_on_error
        self.executor = ToolExecutor(mcp_client)

    async def run_async(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract content from specified pages.

        Args:
            page_ids: List of page IDs to extract content from
            context: Optional context information (e.g., {"purpose": "Import as sources"})

        Returns:
            ExtractionResult with list of ExtractedPage objects
        """
        execution_history: List[ExecutionStep] = []
        iteration = 0

        try:
            # Connect to MCP server
            await self.mcp_client.connect()
            logger.info("Connected to MCP server for extraction")

            if self.verbose:
                print("\n" + "=" * 70)
                print("📄 MCP Extract Agent Starting")
                print("=" * 70)
                print(f"Page IDs: {page_ids}")
                print(f"Context: {context}")
                print(f"Max iterations: {self.max_iterations}")

            # Get available tools
            available_tools = await self.executor.get_available_tools()
            logger.info(f"Discovered {len(available_tools)} available tools")

            # ReAct loop
            while iteration < self.max_iterations:
                iteration += 1

                if self.verbose:
                    print(f"\n{'=' * 70}")
                    print(f"Iteration {iteration}/{self.max_iterations}")
                    print("=" * 70)

                # Execute one iteration
                step, should_finish = await self._execute_iteration(
                    page_ids, context, available_tools, execution_history, iteration
                )

                execution_history.append(step)

                # Check if we should finish
                if should_finish:
                    if self.verbose:
                        print(f"\n✓ Extract agent finished after {iteration} iteration(s)")

                    # Parse the final answer as JSON
                    if step.action == "finish" and step.tool_results:
                        final_answer = step.tool_results[0].content
                        pages = self._parse_extraction_results(final_answer)

                        return ExtractionResult(
                            pages=pages,
                            total_extracted=len(pages),
                            execution_history=execution_history,
                            iterations_used=iteration,
                            success=True,
                        )

            # Max iterations reached
            if self.verbose:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached")

            return ExtractionResult(
                pages=[],
                total_extracted=0,
                execution_history=execution_history,
                iterations_used=iteration,
                success=False,
                error="Max iterations reached without completing the extraction",
            )

        except Exception as e:
            error_msg = f"Extract agent execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.verbose:
                print(f"\n❌ Error: {error_msg}")

            return ExtractionResult(
                pages=[],
                total_extracted=0,
                execution_history=execution_history,
                iterations_used=iteration,
                success=False,
                error=error_msg,
            )

        finally:
            await self.mcp_client.disconnect()
            logger.info("Disconnected from MCP server")

    def run(
        self, page_ids: List[str], context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract content (synchronous wrapper).

        Args:
            page_ids: List of page IDs to extract content from
            context: Optional context information

        Returns:
            ExtractionResult with list of ExtractedPage objects
        """
        return asyncio.run(self.run_async(page_ids, context))

    async def _execute_iteration(
        self,
        page_ids: List[str],
        context: Optional[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
        iteration: int,
    ) -> tuple[ExecutionStep, bool]:
        """Execute a single ReAct iteration."""
        # Build the prompt
        prompt = self._build_extract_prompt(page_ids, context, available_tools, execution_history)

        logger.info(f"[EXTRACT_AGENT] Iteration {iteration}: Sending prompt to LLM")

        if self.verbose:
            print("\n💭 Reasoning...")

        # Get structured response from LLM
        try:
            response = self.llm.generate(
                prompt=prompt, system_prompt=self.EXTRACT_SYSTEM_PROMPT, schema=AgentAction
            )

            # Parse the response
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                import json

                action = AgentAction(**json.loads(response))

            logger.info(
                f"[EXTRACT_AGENT] Iteration {iteration}: Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )

        except Exception as e:
            logger.error(f"[EXTRACT_AGENT] Failed to get structured response: {e}", exc_info=True)
            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=f"Error: Failed to parse LLM response: {str(e)}",
                    action="finish",
                    tool_calls=[],
                    tool_results=[
                        ToolResult(
                            tool_name="llm_error",
                            success=False,
                            error=str(e),
                        )
                    ],
                ),
                True,
            )

        if self.verbose:
            print(f"\n   Reasoning: {action.reasoning}")
            print(f"   Action: {action.action}")

        # Handle finish action
        if action.action == "finish":
            logger.info("[EXTRACT_AGENT] Agent finishing with extracted content")

            if self.verbose:
                print(f"\n✓ Final Answer: {action.final_answer[:200]}...")

            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=action.reasoning,
                    action="finish",
                    tool_calls=[],
                    tool_results=[
                        ToolResult(
                            tool_name="finish",
                            success=True,
                            content=action.final_answer or "",
                        )
                    ],
                ),
                True,
            )

        # Handle tool calls
        if action.action == "call_tool":
            if not action.tool_calls:
                logger.warning("Action is 'call_tool' but no tool_calls provided")
                return (
                    ExecutionStep(
                        iteration=iteration,
                        reasoning=action.reasoning,
                        action="call_tool",
                        tool_calls=[],
                        tool_results=[
                            ToolResult(
                                tool_name="error",
                                success=False,
                                error="No tool calls specified",
                            )
                        ],
                    ),
                    False,
                )

            tool_names = [tc.tool_name for tc in action.tool_calls]
            logger.info(f"[EXTRACT_AGENT] Calling {len(action.tool_calls)} tool(s): {tool_names}")

            if self.verbose:
                print(f"\n🔧 Calling {len(action.tool_calls)} tool(s):")
                for tc in action.tool_calls:
                    print(f"   • {tc.tool_name}")

            # Execute all tool calls
            tool_results: List[ToolResult] = []
            for tool_call in action.tool_calls:
                result = await self.executor.execute_tool(tool_call)
                tool_results.append(result)

                if result.success:
                    logger.info(
                        f"[EXTRACT_AGENT] Tool {result.tool_name} succeeded, "
                        f"returned {len(result.content)} chars"
                    )
                else:
                    logger.error(f"[EXTRACT_AGENT] Tool {result.tool_name} failed: {result.error}")

                if self.verbose:
                    if result.success:
                        print(f"      ✓ {result.tool_name}: {len(result.content)} chars")
                    else:
                        print(f"      ✗ {result.tool_name}: {result.error}")

                # Check for errors
                if not result.success and self.stop_on_error:
                    raise RuntimeError(f"Tool '{result.tool_name}' failed: {result.error}")

            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=action.reasoning,
                    action="call_tool",
                    tool_calls=action.tool_calls,
                    tool_results=tool_results,
                ),
                False,
            )

        # Unknown action
        logger.warning(f"Unknown action: {action.action}")
        return (
            ExecutionStep(
                iteration=iteration,
                reasoning=action.reasoning,
                action=action.action,
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="error",
                        success=False,
                        error=f"Unknown action: {action.action}",
                    )
                ],
            ),
            True,
        )

    def _build_extract_prompt(
        self,
        page_ids: List[str],
        context: Optional[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
    ) -> str:
        """Build the extraction prompt with history and available tools."""
        # Format available tools
        tools_description = []
        for tool in available_tools:
            tool_desc = f"- {tool['name']}: {tool.get('description', 'No description')}"
            if "inputSchema" in tool and tool["inputSchema"]:
                schema = tool["inputSchema"]
                if "properties" in schema:
                    params = ", ".join(schema["properties"].keys())
                    tool_desc += f"\n  Parameters: {params}"
            tools_description.append(tool_desc)

        tools_text = "\n".join(tools_description)

        # Format execution history
        history_text = ""
        if execution_history:
            history_parts = []
            for step in execution_history:
                history_parts.append(f"Iteration {step.iteration}:")
                history_parts.append(f"  Reasoning: {step.reasoning}")
                history_parts.append(f"  Action: {step.action}")

                if step.tool_calls:
                    history_parts.append("  Tools called:")
                    for tc in step.tool_calls:
                        history_parts.append(f"    • {tc.tool_name}")

                if step.tool_results:
                    history_parts.append("  Results:")
                    for tr in step.tool_results:
                        if tr.success:
                            content_preview = (
                                tr.content[:200] + "..." if len(tr.content) > 200 else tr.content
                            )
                            history_parts.append(f"    • {tr.tool_name}: {content_preview}")
                        else:
                            history_parts.append(f"    • {tr.tool_name}: ERROR - {tr.error}")

                history_parts.append("")

            history_text = "\n".join(history_parts)

        # Build the full prompt
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
            prompt += """This is the first iteration. Extract full content from all specified pages.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking
- action: Either "call_tool" (to fetch content) or "finish" (when you have all content)
- tool_calls: List of tools to call if action="call_tool"
- final_answer: JSON with extracted pages if action="finish"

Then, return the pages with full content in the JSON format specified in the system prompt."""

        return prompt

    def _parse_extraction_results(self, final_answer: str) -> List[ExtractedPage]:
        """Parse the LLM's final answer into ExtractedPage objects."""
        try:
            # Try to parse as JSON
            data = json.loads(final_answer)

            # Extract pages array
            if isinstance(data, dict) and "pages" in data:
                pages_data = data["pages"]
            elif isinstance(data, list):
                pages_data = data
            else:
                logger.warning(f"Unexpected data format: {type(data)}")
                return []

            # Convert to ExtractedPage objects
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
                    logger.warning(f"Page data: {page_data}")
                    continue

            return pages

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction results as JSON: {e}")
            logger.error(f"Final answer: {final_answer}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing extraction results: {e}")
            return []
