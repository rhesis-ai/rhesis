"""
Example: Using Autonomous MCP Agent

This demonstrates how to use the autonomous MCPAgent to intelligently
extract content from any MCP server (Notion, Slack, GitHub, etc.) using
natural language queries.

The agent autonomously:
- Discovers available tools from the MCP server
- Reasons about which tools to use
- Executes tools iteratively
- Synthesizes a final answer
"""

import os

from rhesis.sdk.models import get_model
from rhesis.sdk.services import MCPAgent, MCPClientManager

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system environment variables


def main():
    """Example using Google Gemini with Notion MCP server."""
    print("=" * 70)
    print("Autonomous MCP Agent Example")
    print("=" * 70)

    # Initialize LLM with Gemini
    # Available models: gemini-2.0-flash, gemini-1.5-pro-latest, gemini-pro
    llm = get_model(
        provider="gemini",
        model_name="gemini-2.0-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    # Create MCP client for Notion
    manager = MCPClientManager()
    mcp_client = manager.create_client("notionApi")

    # Create autonomous agent
    # The agent will figure out what tools to use based on the query
    # It's trained to be efficient: search first, get metadata, then selectively retrieve content
    agent = MCPAgent(
        llm=llm,
        mcp_client=mcp_client,
        max_iterations=10,  # Maximum number of reasoning iterations
        verbose=True,  # Show detailed execution information
        stop_on_error=True,  # Stop immediately on any error (default: True)
    )

    # User query - the agent figures out the rest autonomously!
    user_query = """
    I remember that Asad wrote a blog post about hosting Rhesis locally.
    I cannot find it now. Can you give me the full content of the blog post?
    """

    print(f"\nUser Query: {user_query.strip()}\n")

    # Single call - agent does everything autonomously
    result = agent.run(user_query)

    # Display results
    if result.success:
        print("\n" + "=" * 70)
        print("Final Answer:")
        print("=" * 70)
        print(result.final_answer)

        # Show execution metadata
        print("\n" + "=" * 70)
        print("Execution Summary:")
        print("=" * 70)
        print(f"Success: {result.success}")
        print(f"Iterations used: {result.iterations_used}")
        print(f"Max iterations reached: {result.max_iterations_reached}")
        print(f"Total steps: {len(result.execution_history)}")

        # Show execution history
        if result.execution_history:
            print("\n" + "=" * 70)
            print("Execution History:")
            print("=" * 70)
            for step in result.execution_history:
                print(f"\nIteration {step.iteration}:")
                print(f"  Action: {step.action}")
                print(f"  Reasoning: {step.reasoning}...")  # First 100 chars
                if step.tool_calls:
                    print(f"  Tools called: {[tc.tool_name for tc in step.tool_calls]}")

        print("\n✓ Agent completed successfully!")

    else:
        print("\n" + "=" * 70)
        print("Agent Failed")
        print("=" * 70)
        print(f"Error: {result.error}")
        print(f"Iterations used: {result.iterations_used}")


def example_with_other_providers():
    """
    Additional examples with other LLM providers.

    You can easily swap Gemini for any of these providers:
    """
    print("\n\nOther Available Providers:")
    print("=" * 70)

    examples = """
    # OpenAI
    llm = get_model(provider="openai", model_name="gpt-4o-mini")

    # Anthropic Claude
    llm = get_model(provider="anthropic", model_name="claude-3-5-sonnet-20241022")

    # Groq (fast & free)
    llm = get_model(provider="groq", model_name="llama-3.1-70b-versatile")

    # Gemini (current)
    llm = get_model(provider="gemini", model_name="gemini-2.0-flash")

    # Create MCP client (works with any MCP server!)
    manager = MCPClientManager()
    mcp_client = manager.create_client("notionApi")  # or "github", "slack", etc.

    # All use the same autonomous agent interface!
    agent = MCPAgent(llm=llm, mcp_client=mcp_client, max_iterations=10, verbose=True)
    result = agent.run("Your natural language query here")
    """
    print(examples)


def example_with_different_mcp_servers():
    """
    Example showing how to use different MCP servers.

    The agent is server-agnostic - just change the server name!
    """
    print("\n\nUsing Different MCP Servers:")
    print("=" * 70)

    examples = """
    # Notion
    mcp_client = manager.create_client("notionApi")
    agent = MCPAgent(llm=llm, mcp_client=mcp_client)
    result = agent.run("Find my team's meeting notes from last week")

    # GitHub
    mcp_client = manager.create_client("github")
    agent = MCPAgent(llm=llm, mcp_client=mcp_client)
    result = agent.run("List recent pull requests in the main repo")

    # Slack
    mcp_client = manager.create_client("slack")
    agent = MCPAgent(llm=llm, mcp_client=mcp_client)
    result = agent.run("Get messages from the #engineering channel today")

    The agent automatically discovers available tools and uses them appropriately!
    """
    print(examples)


if __name__ == "__main__":
    # Check if Gemini API key is available
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not found in environment")
        print("\nTo run this example, set your API key:")
        print("  export GEMINI_API_KEY=your_key_here")
        print("\nOr add it to your .env file:")
        print('  echo "GEMINI_API_KEY=your_key_here" >> .env')
        print("\nYou can also use other providers:")
        print("  - OpenAI: export OPENAI_API_KEY=your_key")
        print("  - Anthropic: export ANTHROPIC_API_KEY=your_key")
        print("  - Groq: export GROQ_API_KEY=your_key")
    else:
        main()
        # Uncomment to see additional examples:
        # example_with_other_providers()
        # example_with_different_mcp_servers()
