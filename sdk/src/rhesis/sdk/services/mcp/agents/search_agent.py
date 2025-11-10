"""MCP Search Agent for finding and listing pages from any MCP server."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    ExecutionStep,
    PageMetadata,
    SearchResult,
    ToolResult,
)

logger = logging.getLogger(__name__)


class MCPSearchAgent:
    """
    Agent for searching and listing pages from any MCP server.

    This agent uses LLM-based normalization to transform diverse service responses
    (Notion, GitHub, Slack, etc.) into a unified PageMetadata schema.
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

    def __init__(
        self,
        llm: BaseLLM,
        mcp_client: MCPClient,
        max_iterations: int = 10,
        verbose: bool = False,
        stop_on_error: bool = True,
    ):
        """
        Initialize the MCP Search Agent.

        Args:
            llm: An instance of BaseLLM
            mcp_client: MCP client instance
            max_iterations: Maximum number of ReAct iterations (default: 10)
            verbose: If True, prints detailed execution information
            stop_on_error: If True, raises exception on errors (default: True)
        """
        self.llm = llm
        self.mcp_client = mcp_client
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.stop_on_error = stop_on_error
        self.executor = ToolExecutor(mcp_client)

    async def run_async(self, query: str) -> SearchResult:
        """
        Execute search and return unified SearchResult.

        Args:
            query: Natural language search query

        Returns:
            SearchResult with list of PageMetadata objects
        """
        execution_history: List[ExecutionStep] = []
        iteration = 0

        try:
            # Connect to MCP server
            await self.mcp_client.connect()
            logger.info("Connected to MCP server for search")

            if self.verbose:
                print("\n" + "=" * 70)
                print("🔍 MCP Search Agent Starting")
                print("=" * 70)
                print(f"Query: {query}")
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
                    query, available_tools, execution_history, iteration
                )

                execution_history.append(step)

                # Check if we should finish
                if should_finish:
                    if self.verbose:
                        print(f"\n✓ Search agent finished after {iteration} iteration(s)")

                    # Parse the final answer as JSON and validate against actual results
                    if step.action == "finish" and step.tool_results:
                        final_answer = step.tool_results[0].content
                        pages = self._parse_search_results(final_answer)

                        return SearchResult(
                            pages=pages,
                            total_found=len(pages),
                            query=query,
                            execution_history=execution_history,
                            iterations_used=iteration,
                            success=len(pages) > 0,  # Only successful if we found pages
                            error=None
                            if len(pages) > 0
                            else "No valid pages found in search results",
                        )

            # Max iterations reached
            if self.verbose:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached")

            return SearchResult(
                pages=[],
                total_found=0,
                query=query,
                execution_history=execution_history,
                iterations_used=iteration,
                success=False,
                error="Max iterations reached without completing the search",
            )

        except Exception as e:
            error_msg = f"Search agent execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.verbose:
                print(f"\n❌ Error: {error_msg}")

            return SearchResult(
                pages=[],
                total_found=0,
                query=query,
                execution_history=execution_history,
                iterations_used=iteration,
                success=False,
                error=error_msg,
            )

        finally:
            await self.mcp_client.disconnect()
            logger.info("Disconnected from MCP server")

    def run(self, query: str) -> SearchResult:
        """
        Execute search (synchronous wrapper).

        Args:
            query: Natural language search query

        Returns:
            SearchResult with list of PageMetadata objects
        """
        return asyncio.run(self.run_async(query))

    async def _execute_iteration(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
        iteration: int,
    ) -> tuple[ExecutionStep, bool]:
        """Execute a single ReAct iteration."""
        # Build the prompt
        prompt = self._build_search_prompt(query, available_tools, execution_history)

        logger.info(f"[SEARCH_AGENT] Iteration {iteration}: Sending prompt to LLM")

        if self.verbose:
            print("\n💭 Reasoning...")

        # Get structured response from LLM
        try:
            response = self.llm.generate(
                prompt=prompt, system_prompt=self.SEARCH_SYSTEM_PROMPT, schema=AgentAction
            )

            # Parse the response
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                import json

                action = AgentAction(**json.loads(response))

            logger.info(
                f"[SEARCH_AGENT] Iteration {iteration}: Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )

        except Exception as e:
            logger.error(f"[SEARCH_AGENT] Failed to get structured response: {e}", exc_info=True)
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
            logger.info("[SEARCH_AGENT] Agent finishing with results")

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
            logger.info(f"[SEARCH_AGENT] Calling {len(action.tool_calls)} tool(s): {tool_names}")

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
                        f"[SEARCH_AGENT] Tool {result.tool_name} succeeded, "
                        f"returned {len(result.content)} chars"
                    )
                else:
                    logger.error(f"[SEARCH_AGENT] Tool {result.tool_name} failed: {result.error}")

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

    def _build_search_prompt(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
    ) -> str:
        """Build the search prompt with history and available tools."""
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
                            # For search: include full content so LLM can extract all
                            # For other ops: truncate to avoid token bloat
                            if len(tr.content) > 10000:
                                # Very large response - include first 5000 chars
                                truncated_note = f"\n... (truncated, total {len(tr.content)} chars)"
                                content_preview = tr.content[:5000] + truncated_note
                            else:
                                # Include full content for better extraction
                                content_preview = tr.content
                            history_parts.append(f"    • {tr.tool_name}: {content_preview}")
                        else:
                            history_parts.append(f"    • {tr.tool_name}: ERROR - {tr.error}")

                history_parts.append("")

            history_text = "\n".join(history_parts)

        # Build the full prompt
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

    def _parse_search_results(self, final_answer: str) -> List[PageMetadata]:
        """Parse the LLM's final answer into PageMetadata objects."""
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

            # Convert to PageMetadata objects
            pages = []
            for page_data in pages_data:
                try:
                    page = PageMetadata(**page_data)
                    pages.append(page)
                except Exception as e:
                    logger.warning(f"Failed to parse page metadata: {e}")
                    logger.warning(f"Page data: {page_data}")
                    continue

            return pages

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse search results as JSON: {e}")
            logger.error(f"Final answer: {final_answer}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing search results: {e}")
            return []
