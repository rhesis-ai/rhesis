# Autonomous MCP Agent

An intelligent agent that autonomously uses LLMs to discover and execute tools from any MCP (Model Context Protocol) server.

## What It Does

The agent operates in a **ReAct loop** (Reasoning + Action):
1. **Reason**: Thinks about what information it needs
2. **Act**: Decides which tools to call (or when to finish)
3. **Observe**: Examines tool results
4. **Repeat**: Continues until the task is complete

You give it a natural language query, and it figures out everything else autonomously!

## Quick Start

### 1. Set your API key

```bash
echo "GEMINI_API_KEY=your_key_here" >> .env
```

### 2. Run the example

```bash
python examples/mcp_agent_example.py
```

## Basic Usage

### Simple Autonomous Query

```python
from rhesis.sdk.models import get_model
from rhesis.sdk.services import MCPAgent, MCPClientManager

# Initialize any LLM provider
llm = get_model(provider="gemini", model_name="gemini-2.0-flash")

# Create MCP client for any server (Notion, GitHub, Slack, etc.)
manager = MCPClientManager()
mcp_client = manager.create_client("notionApi")

# Create autonomous agent
agent = MCPAgent(
    llm=llm,
    mcp_client=mcp_client,
    max_iterations=10,  # Maximum reasoning iterations
    verbose=True        # Show execution details
)

# Single query - agent does everything autonomously!
result = agent.run("Find the PRD document and extract the main concept")

# Access results
print(result.final_answer)
print(f"Iterations: {result.iterations_used}")
print(f"Success: {result.success}")
```

## Architecture

### Components

**1. MCPAgent** (`sdk/src/rhesis/sdk/services/mcp/agent.py`)
- Autonomous reasoning agent
- Executes ReAct loop
- Makes decisions about tool usage
- Synthesizes final answer

**2. ToolExecutor** (`sdk/src/rhesis/sdk/services/mcp/executor.py`)
- Stateless execution layer
- Executes tool calls
- Returns structured results
- No business logic

**3. MCPClient** (`sdk/src/rhesis/sdk/services/mcp/client.py`)
- Connects to MCP servers
- Discovers available tools
- Executes tool calls via MCP protocol

**4. Schemas** (`sdk/src/rhesis/sdk/services/mcp/schemas.py`)
- Pydantic models for structured output
- `AgentAction`: LLM's reasoning and action
- `ToolCall`: Tool invocation
- `ToolResult`: Execution result
- `AgentResult`: Final output

### How It Works

```
User Query → Agent
              ↓
         [ReAct Loop]
              ↓
    1. Discover tools from MCP server
    2. Reason about what to do
    3. Call tools via ToolExecutor
    4. Observe results
    5. Repeat until finished
              ↓
         Final Answer
```

## Supported LLM Providers

The agent works with **any** LLM provider:

```python
# Gemini (recommended for cost/performance)
llm = get_model(provider="gemini", model_name="gemini-2.0-flash")

# OpenAI
llm = get_model(provider="openai", model_name="gpt-4o-mini")

# Anthropic Claude
llm = get_model(provider="anthropic", model_name="claude-3-5-sonnet-20241022")

# Groq (fast & free)
llm = get_model(provider="groq", model_name="llama-3.1-70b-versatile")

# All use the same MCPAgent interface!
agent = MCPAgent(llm=llm, mcp_client=mcp_client)
```

## Supported MCP Servers

The agent is **server-agnostic** - just configure the server in your `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "notionApi": {
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": { "NOTION_API_KEY": "your_key" }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@github/mcp-server"],
      "env": { "GITHUB_TOKEN": "your_token" }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@slack/mcp-server"],
      "env": { "SLACK_TOKEN": "your_token" }
    }
  }
}
```

Then use any server:

```python
# Notion
mcp_client = manager.create_client("notionApi")

# GitHub
mcp_client = manager.create_client("github")

# Slack
mcp_client = manager.create_client("slack")

# Agent works the same way with any server!
agent = MCPAgent(llm=llm, mcp_client=mcp_client)
```

## Agent Configuration

```python
agent = MCPAgent(
    llm=llm,                    # Required: LLM instance
    mcp_client=mcp_client,      # Required: MCP client
    max_iterations=10,          # Max reasoning iterations (default: 10)
    verbose=True,               # Print execution details (default: False)
    system_prompt=None,         # Custom system prompt (optional)
)
```

## Result Object

```python
result = agent.run("Your query here")

# AgentResult attributes:
result.final_answer            # str: The agent's final answer
result.success                 # bool: Whether execution succeeded
result.iterations_used         # int: Number of iterations executed
result.max_iterations_reached  # bool: Whether limit was hit
result.execution_history       # List[ExecutionStep]: Full history
result.error                   # Optional[str]: Error message if failed

# Execution history details:
for step in result.execution_history:
    print(f"Iteration {step.iteration}")
    print(f"  Reasoning: {step.reasoning}")
    print(f"  Action: {step.action}")
    print(f"  Tools: {[tc.tool_name for tc in step.tool_calls]}")
    print(f"  Results: {step.tool_results}")
```

## Advanced Usage

### Custom System Prompt

```python
custom_prompt = """You are a specialized agent for extracting technical documentation.

Focus on:
- API endpoints and their parameters
- Code examples
- Configuration options

Be thorough and include all technical details."""

agent = MCPAgent(
    llm=llm,
    mcp_client=mcp_client,
    system_prompt=custom_prompt
)
```

### Error Handling

```python
result = agent.run("Find information about XYZ")

if result.success:
    print(result.final_answer)
else:
    print(f"Agent failed: {result.error}")
    print(f"Completed {result.iterations_used} iterations")

    # Examine history to see where it failed
    for step in result.execution_history:
        for tool_result in step.tool_results:
            if not tool_result.success:
                print(f"Tool {tool_result.tool_name} failed: {tool_result.error}")
```

### Multiple Queries

```python
# The agent maintains no state between runs
queries = [
    "Find all PRD documents",
    "Extract API documentation",
    "List recent meeting notes"
]

for query in queries:
    result = agent.run(query)
    print(f"Query: {query}")
    print(f"Answer: {result.final_answer}\n")
```

## What Makes This Different?

- ✅ **Fully Autonomous** - No manual tool selection needed
- ✅ **ReAct Loop** - Intelligent reasoning and action
- ✅ **Server Agnostic** - Works with any MCP server
- ✅ **LLM Agnostic** - Works with any LLM provider
- ✅ **Structured Output** - Uses Pydantic schemas for reliability
- ✅ **Error Handling** - Aborts on tool failures
- ✅ **Execution History** - Full transparency into agent's actions
- ✅ **Configurable** - Adjustable max iterations and prompts
- ✅ **Verbose Mode** - See what the agent is doing in real-time

## Files Structure

```
sdk/src/rhesis/sdk/services/mcp/
├── __init__.py       # Exports
├── agent.py          # MCPAgent with ReAct loop
├── client.py         # MCPClient for MCP protocol
├── executor.py       # ToolExecutor for pure execution
└── schemas.py        # Pydantic schemas

examples/
└── mcp_agent_example.py   # Usage example
```

## Verbose Mode Output

When `verbose=True`, you'll see:

```
======================================================================
🤖 MCP Agent Starting
======================================================================
Query: Find the PRD for MCP Integration

🔧 Discovered 15 available tools

======================================================================
Iteration 1/10
======================================================================

💭 Reasoning...

   Reasoning: I need to search for a page titled 'PRD: MCP Integration'
   Action: call_tool

🔧 Calling 1 tool(s):
   • API-post-search
      ✓ API-post-search: 2453 chars

======================================================================
Iteration 2/10
======================================================================

💭 Reasoning...

   Reasoning: I found the page ID, now I'll fetch its content
   Action: call_tool

🔧 Calling 1 tool(s):
   • API-get-block-children
      ✓ API-get-block-children: 15234 chars

======================================================================
Iteration 3/10
======================================================================

💭 Reasoning...

   Reasoning: I have all the information needed
   Action: finish

✓ Final Answer: [Agent's synthesized answer]

✓ Agent finished after 3 iteration(s)
```

## Next Steps

1. Try different MCP servers (GitHub, Slack, etc.)
2. Experiment with different LLM providers
3. Customize the system prompt for your use case
4. Adjust `max_iterations` based on task complexity
5. Integrate into your application

The agent is fully autonomous and ready to use!
