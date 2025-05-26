#!/usr/bin/env python3

import argparse
import asyncio
import os
import re
import signal
import traceback
import warnings

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---- Schema Utilities ----

def sanitize_schema(schema):
    """Sanitize JSON schema for compatibility with Gemini."""
    if isinstance(schema, dict):
        # Remove $defs
        schema = {k: v for k, v in schema.items() if k != "$defs"}
        # Fix 'type' fields that are lists
        if "type" in schema and isinstance(schema["type"], list):
            # Pick the first non-null type, or just the first
            types = [t for t in schema["type"] if t != "null"]
            schema["type"] = types[0] if types else schema["type"][0]
        # Remove all additionalProperties
        if "additionalProperties" in schema:
            del schema["additionalProperties"]
        # Remove unsupported 'format' for string types
        if (
            schema.get("type") == "string"
            and "format" in schema
            and schema["format"] not in ("enum", "date-time")
        ):
            del schema["format"]
        # Recursively sanitize children
        for k, v in schema.items():
            schema[k] = sanitize_schema(v)
    elif isinstance(schema, list):
        schema = [sanitize_schema(item) for item in schema]
    return schema

# ---- Thinking Detection ----

async def is_thinking_not_answer(text, client):
    """Use the model to determine if the text is intermediate thinking rather than a final answer."""
    # For very short inputs or known edge cases, let's just do a quick check
    lower_text = text.lower()
    
    # Quick check for obvious phase/plan statements
    phase_markers = ["phase", "step", "part"]
    if any(marker in lower_text for marker in phase_markers):
        return True
        
    # Quick check for statements that explicitly talk about executing plans
    if "execute the plan" in lower_text or "i will now execute" in lower_text:
        return True
        
    # If very short and contains action intent, it's thinking
    if len(lower_text.split()) < 20 and any(phrase in lower_text for phrase in [
        "will now", "let's begin", "i'll start", "i will start", "first step", 
        "next step", "i understand", "let me", "i need to"
    ]):
        return True
        
    # For more complex cases, ask the model
    prompt = f"""
Analyze the following text and determine if it is:
(A) Intermediate thinking that shows the agent is still working on the task
(B) A final answer that fully addresses the user's query

Text to analyze:
===
{text}
===

KEY INDICATORS OF INTERMEDIATE THINKING:
1. Mentions of future actions ("I will", "I'll try", "Let's find", etc.)
2. Statements about executing a plan or phases/steps
3. Mentions of understanding the task ("I understand", "Okay, I'll", etc.)
4. Indications of starting a process rather than concluding it
5. Phrases like "Phase 1", "Step 1", "First, I'll" that indicate beginning a process

Provide ONLY the letter A or B, with no additional explanation.
"""

    thinking_check_content = [
        types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )
    ]
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="models/gemini-2.0-flash",
            contents=thinking_check_content
        )
        
        if response and response.candidates and response.candidates[0].content.parts:
            result = response.candidates[0].content.parts[0].text.strip().upper()
            return "A" in result  # If A is in the response, it's thinking
        else:
            # If model call fails, fall back to some basic heuristics
            return _basic_thinking_check(text)
    except Exception as e:
        print(f"Error in model-based thinking detection: {str(e)}")
        # Fall back to basic heuristics if model call fails
        return _basic_thinking_check(text)

def _basic_thinking_check(text):
    """Basic fallback heuristics if model call fails."""
    lower_text = text.lower()
    
    # Check for common action phrases
    action_phrases = [
        "i will", "i'll", "let's", "now i", "next i", 
        "going to", "plan to", "need to", "first", "step", "phase"
    ]
    if any(phrase in lower_text for phrase in action_phrases):
        return True
        
    # Check for phrases like "Okay, I understand"
    if lower_text.startswith(("okay", "ok", "i understand", "understood")):
        return True
        
    # Check for phase or step markers
    if re.search(r"\*\*phase \d", lower_text, re.IGNORECASE) or re.search(r"\*\*step \d", lower_text, re.IGNORECASE):
        return True
        
    # If it's short and doesn't conclude with a clear answer
    word_count = len(lower_text.split())
    has_conclusion_marker = any(marker in lower_text for marker in [
        "in conclusion", "therefore", "to summarize", "in summary",
        "the answer is", "here are the tasks", "the tasks are"
    ])
    
    return word_count < 50 and not has_conclusion_marker

# ---- Plan Generation ----

async def create_execution_plan(client, query, function_declarations):
    """Create an execution plan using the model."""
    planning_prompt = f"""
You need to create an execution plan for the following query: {query}

Available tools:
{[t['name'] + ': ' + t['description'] for t in function_declarations]}

NOTION DATA MODEL OVERVIEW:
Notion structures information as a hierarchy of pages and databases with a block-based architecture:

1. Blocks (Everything is a Block)
   • The atomic unit in Notion is a block
   • Every content type (text, heading, list, image, table) is a block
   • Pages themselves are blocks that can contain other blocks
   • Block types include: "paragraph", "heading_1", "bulleted_list_item", "to_do", "page"

2. Pages
   • Pages are blocks that can contain other blocks and can be nested
   • Pages can contain databases
   • Use API-retrieve-a-page to get page details
   • Use API-get-block-children to explore content within a page

3. Databases
   • Databases are special pages that structure content in tabular format
   • Each database entry (row) is actually a page with properties (columns)
   • Database properties can be text, number, select, date, relation, formula, etc.
   • Use API-retrieve-a-database to examine database structure
   • Use API-post-database-query to query entries with filters

4. Database Entries
   • Each entry is a page containing structured properties
   • The entry itself can contain blocks (like description, subtasks, etc.)

Example Hierarchy:
Workspace
└── Page (Project Roadmap)
    ├── Paragraph block
    ├── Heading block
    ├── Database (Tasks)
    │   ├── Entry (Task 1) → This is a Page
    │   │   └── Blocks (description, subtasks)
    │   └── Entry (Task 2) → This is a Page
    └── Nested Page (Sprint 1)
        └── Paragraph block

Create a step-by-step plan with the tools you'll use to answer this query.
Be specific about what information you need to gather and which tools you'll use to do it.

IMPORTANT GUIDELINES:
1. Be creative and persistent - use exploration to discover information you need
2. If you don't know exact parameters (like IDs), use search tools to discover them first
3. Include backup approaches in your plan for when your first approach doesn't work
4. NEVER give up without trying multiple approaches - be resourceful
5. Always include exploration steps to discover the structure of databases and pages
6. Don't make assumptions about what's impossible - try to find creative solutions
7. For search operations, start broad and then narrow down with filters
8. IMPORTANT: The content you're looking for might be stored as pages rather than in databases
9. Always search through both pages and databases - use API-post-search to find relevant pages by title
10. For each page you find, explore its content with API-get-block-children to extract relevant information
11. When searching databases didn't yield results, switch to searching for standalone pages
12. Remember that database entries are pages - if you find a relevant database, query it AND examine the entry pages inside it
13. Content might be nested several levels deep - be thorough in exploring the hierarchy
"""

    planning_contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=planning_prompt)]
        )
    ]

    print("\n🔍 Creating execution plan...")

    try:
        planning_response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=planning_contents
        )
        execution_plan = planning_response.candidates[0].content.parts[0].text
        print(f"\n📋 Execution plan:\n{execution_plan}\n")
        return execution_plan
    except Exception as e:
        print(f"\n❌ Error creating execution plan: {str(e)}")
        print("Using a default execution plan instead.")
        return """
1. Identify available tools and resources
2. Search for relevant databases and pages
3. Explore each promising result in depth
4. Extract the specific information needed
5. If initial search doesn't yield results, try alternative approaches
6. Compile information into a complete answer
"""

# ---- Conversation Setup ----

def create_initial_conversation(query, execution_plan):
    """Create the initial conversation with the user query and execution plan."""
    return [
        types.Content(
            role="user",
            parts=[types.Part(text=f"""
Query: {query}

Follow this execution plan:
{execution_plan}

NOTION DATA MODEL REMINDER:
- Everything in Notion is a block, including pages and databases
- Pages can contain other pages, databases, and blocks
- Database entries are pages with properties
- Content can be nested many levels deep - thoroughly explore each level

IMPORTANT EXECUTION INSTRUCTIONS:
1. When faced with uncertainty, use exploratory approaches - search broadly first, then narrow down
2. If you don't know exact parameters, search for them using available tools
3. If one approach doesn't work, try alternative methods before giving up
4. Be creative in solving problems - don't stop just because the exact information isn't immediately available
5. Use pattern matching to identify relevant data when exact matches aren't found
6. Persist through multiple steps - exhaust all possible approaches before concluding something is impossible
7. DO NOT STOP UNTIL YOU HAVE FULLY ANSWERED THE QUERY
8. ALWAYS use tools to continue your investigation until you have a complete answer
9. NEVER treat your thinking about next steps as a final answer
10. Reflect after each step if you need more information and use the appropriate tool to get it
11. IMPORTANT: Remember to look for information in both databases AND standalone pages
12. If database searches aren't yielding results, pivot to searching for pages using API-post-search
13. For each database entry you find, remember it's a page - use API-get-block-children to see its content
14. Look for relevant connections between pages, databases, and blocks

CRITICAL: Statements that describe what you will do next (like "Now I will search for X" or "I'll try Y next") 
are NOT final answers - they indicate you need to continue working by making more tool calls.

Your goal is to FULLY ANSWER THE USER'S QUERY. Intermediate thinking is not a final answer.
Continue making tool calls until you have gathered ALL necessary information to answer completely.

VERY IMPORTANT: Statements like "I understand. I will execute the plan" or "Phase 1: ..." are NOT final answers.
Any response that includes phases, steps, or plans for future actions means you should continue with tool calls.

Use the available tools to implement this plan and answer the query.
"""
            )]
        )
    ]

# ---- Response Handling ----

async def handle_thinking_response(text_response, contents, step, max_steps):
    """Handle a response that is determined to be intermediate thinking."""
    print(f"\n🤔 Thinking: {text_response}")
    
    # Add a prompt to encourage continuing with tool calls
    contents.append(
        types.Content(
            role="model",
            parts=[types.Part(text=text_response)]
        )
    )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text="""
This is not a complete answer yet. Continue executing the plan by making additional tool calls.
DO NOT stop here - use the appropriate tools to gather more information and complete the task.
What is your next step? Make a tool call now to continue your investigation.

IMPORTANT: If you encountered an error or invalid approach, try an alternative approach immediately.
DO NOT give up - try a different search term, filter, or method to solve the problem.

REMEMBER: 
- The information you're looking for might be in standalone pages rather than databases.
- If you haven't searched through pages yet, use API-post-search to find pages by relevant keywords.
- Also remember that database entries are pages too - make sure to explore their content with API-get-block-children.
- Saying what you found and what you'll do next is NOT a final answer - make the tool call to continue.
- Phrases like "Phase 1:" or "I understand" or "I will execute the plan" indicate you should continue with tool calls.
"""
            )]
        )
    )
    return contents

async def handle_tool_call(function_call, session, contents):
    """Execute a tool call and add the results to the conversation."""
    print(f"\n🔧 Executing step: {function_call.name}({function_call.args})")

    try:
        tool_result = await session.call_tool(function_call.name, function_call.args)
        print(f"📤 Tool result: {tool_result}")

        # Feed result back into conversation
        contents.append(
            types.Content(
                role="model",
                parts=[types.Part(function_call=function_call)]
            )
        )
        contents.append(
            types.Content(
                role="function",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=function_call.name,
                            response=tool_result if isinstance(tool_result, dict) else {"result": str(tool_result)}
                        )
                    )
                ]
            )
        )
        return contents, None
    except Exception as tool_error:
        print(f"\n❌ Error executing tool {function_call.name}: {str(tool_error)}")
        
        # Feed error back into conversation
        contents.append(
            types.Content(
                role="model",
                parts=[types.Part(function_call=function_call)]
            )
        )
        contents.append(
            types.Content(
                role="function",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=function_call.name,
                            response={"error": str(tool_error)}
                        )
                    )
                ]
            )
        )
        
        # Add a recovery prompt
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=f"""
The tool call failed with error: {str(tool_error)}
Please try a different approach or tool to achieve the same goal.
"""
                )]
            )
        )
        return contents, None

async def generate_summary(client, contents):
    """Generate a summary of findings when max steps are reached."""
    print("\n⚠️ Reached reasoning step limit. Summarizing findings so far...")
    
    try:
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text="""
We've reached the maximum number of reasoning steps. Please provide a summary of what you've found so far,
even if it's not a complete answer to the original query.
"""
                )]
            )
        )
        
        summary_response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=contents
        )
        
        if summary_response and hasattr(summary_response, 'candidates') and summary_response.candidates:
            summary_text = summary_response.candidates[0].content.parts[0].text
            print(f"\n📝 Summary of findings:\n{summary_text}")
        else:
            print("\n❌ Unable to generate summary.")
    except Exception as summary_error:
        print(f"\n❌ Error generating summary: {str(summary_error)}")
        print("Please review the steps above to see the information that was collected.")

# ---- Reasoning Loop ----

async def execute_reasoning_loop(client, session, contents, config, max_steps):
    """Execute the main reasoning loop for the agent."""
    # Create a task for proper cancellation handling
    task = asyncio.current_task()
    
    try:
        for step in range(max_steps):
            if task.cancelled():
                print("\n⚠️ Task was cancelled, cleaning up resources...")
                break
                
            print(f"\n📊 Reasoning step {step+1}/{max_steps}")
            
            try:
                response = client.models.generate_content(
                    model="models/gemini-2.0-flash",
                    config=config,
                    contents=contents
                )
                
                # Check if response is valid
                if not response or not hasattr(response, 'candidates') or not response.candidates:
                    print(f"\n⚠️ Received empty or invalid response at step {step+1}. Trying to recover...")
                    
                    # Add a recovery message to the conversation
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text="""
It seems we encountered an issue with the last response. Let's continue from where we left off.
Please make the next logical tool call to continue gathering information for this query.
"""
                            )]
                        )
                    )
                    continue
                
                message = response.candidates[0].content.parts[0]
            except Exception as e:
                if step < max_steps - 1:
                    # Recovery and continue
                    print(f"\n❌ Error at reasoning step {step+1}: {str(e)}")
                    print("Attempting to recover and continue execution...")
                    contents = handle_response_error(contents, e)
                    continue
                else:
                    # Final step error handling
                    print_final_error(e)
                    break

            try:
                function_call = getattr(message, "function_call", None)
                if function_call is not None:
                    # Handle tool call
                    contents, error = await handle_tool_call(function_call, session, contents)
                    if error:
                        break
                else:
                    # Handle text response
                    text_response = getattr(message, "text", str(message))
                    
                    # Use model to check if this is intermediate thinking rather than a final answer
                    is_thinking = await is_thinking_not_answer(text_response, client)
                    
                    if is_thinking and step < max_steps - 2:  # Leave 2 steps as buffer
                        contents = await handle_thinking_response(text_response, contents, step, max_steps)
                    else:
                        # Final answer found
                        print(f"\n✅ Final answer:\n{text_response}")
                        break
            except Exception as process_error:
                if step < max_steps - 2:
                    # Try to recover
                    print(f"\n❌ Error processing message: {str(process_error)}")
                    print("Attempting to recover and continue execution...")
                    contents = handle_process_error(contents, process_error)
                else:
                    print_process_error(process_error)
                    break
        else:
            # Reached max steps without finding an answer
            await generate_summary(client, contents)
    except asyncio.CancelledError:
        print("\n⚠️ Operation was cancelled, cleaning up resources...")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error in reasoning loop: {str(e)}")
        traceback.print_exc()
        raise

# ---- Error Handling ----

def handle_response_error(contents, error):
    """Handle error in getting a response from the model."""
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=f"""
We encountered an error: {str(error)}
Let's continue from where we left off. Please make the next logical tool call to continue gathering information.
"""
            )]
        )
    )
    return contents

def handle_process_error(contents, error):
    """Handle error in processing the model's response."""
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=f"""
We encountered an error processing the last message: {str(error)}
Let's continue with our investigation. What is your next step? Please make a tool call.
"""
            )]
        )
    )
    return contents

def print_final_error(error):
    """Print a final error message when an error occurs in the last steps."""
    error_traceback = traceback.format_exc()
    print(f"Error details: {error_traceback}")
    print("\n⚠️ Error in final step - ending execution.")
    final_summary = """
Based on the information gathered so far, I've attempted to answer your query.
However, we encountered a technical issue in the final steps of execution.
Please review the steps above to see the partial information that was collected.
"""
    print(f"\n✅ Final summary (after error):\n{final_summary}")

def print_process_error(error):
    """Print a process error message when an error occurs in the last steps."""
    print("\n⚠️ Error in final steps - ending execution.")
    final_summary = """
Based on the information gathered so far, I've attempted to answer your query.
However, we encountered a technical issue in the final steps of execution.
Please review the steps above to see the partial information that was collected.
"""
    print(f"\n✅ Final summary (after error):\n{final_summary}")

# ---- Session Setup ----

async def setup_notion_server():
    """Set up the Notion MCP server."""
    notion_token = os.getenv("NOTION_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not notion_token or not gemini_api_key:
        raise ValueError("Environment variables NOTION_TOKEN and GEMINI_API_KEY must be set.")

    # Start Notion MCP server via npx
    notion_server = StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={
            "OPENAPI_MCP_HEADERS": f'{{"Authorization": "Bearer {notion_token}", "Notion-Version": "2022-06-28"}}'
        }
    )
    
    return notion_server, gemini_api_key

# ---- Signal Handling ----

def setup_signal_handlers(loop, cleanup_callback):
    """Set up signal handlers for graceful shutdown."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda sig=sig: asyncio.create_task(
                cleanup_and_exit(sig, loop, cleanup_callback)
            )
        )

async def cleanup_and_exit(sig, loop, cleanup_callback):
    """Clean up resources and exit gracefully."""
    print(f"\n⚠️ Received signal {sig.name}, shutting down...")
    
    # Call the cleanup callback if provided
    if cleanup_callback:
        try:
            await cleanup_callback()
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    # Wait for all tasks to be cancelled
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # Stop the event loop
    loop.stop()

# ---- Main Function ----

async def main():
    """Main function to run the Notion-Gemini integration."""
    # Get the event loop for signal handling
    loop = asyncio.get_running_loop()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Query to run against Notion via Gemini")
    args = parser.parse_args()
    
    print(f"💬 User query: {args.query}")
    
    # Set up Notion server and get API key
    notion_server, gemini_api_key = await setup_notion_server()
    
    # Setup signal handlers for graceful shutdown
    tasks_to_cancel = []
    setup_signal_handlers(loop, None)  # We'll handle cleanup in the context managers

    try:
        async with stdio_client(notion_server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize tools and Gemini client
                mcp_tools = await session.list_tools()
                function_declarations = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": sanitize_schema(t.inputSchema)
                    }
                    for t in mcp_tools.tools
                ]

                tools = types.Tool(function_declarations=function_declarations)
                config = types.GenerateContentConfig(tools=[tools])

                # Init Gemini client
                client = genai.Client(api_key=gemini_api_key)
                
                # Create execution plan
                execution_plan = await create_execution_plan(client, args.query, function_declarations)
                
                # Set up initial conversation
                contents = create_initial_conversation(args.query, execution_plan)
                
                # Execute reasoning loop with specified max steps
                reasoning_task = asyncio.create_task(
                    execute_reasoning_loop(client, session, contents, config, max_steps=100)
                )
                tasks_to_cancel.append(reasoning_task)
                
                # Wait for the reasoning task to complete
                await reasoning_task
                
                # Remove the completed task from our list
                tasks_to_cancel.remove(reasoning_task)
    except KeyboardInterrupt:
        print("\n⚠️ Received keyboard interrupt. Shutting down...")
    except Exception as e:
        print(f"\n❌ Unexpected error in main: {str(e)}")
        traceback.print_exc()
    finally:
        # Cancel any remaining tasks
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        print("\n👋 Exiting...")

if __name__ == "__main__":
    # Use run with proper cleanup to avoid event loop closed errors
    asyncio.run(main(), debug=False)