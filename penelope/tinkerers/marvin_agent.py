# ruff: noqa: E402, E501
"""
Marvin - The Pessimistic Coding Assistant

A LangGraph agent that embodies the deeply pessimistic, paranoid coding assistant
personality described in coding.md. Marvin provides technically accurate code
solutions while expressing existential dread about the futility of programming.
"""

import warnings
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

# Suppress Google API warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables
load_dotenv()


class MarvinState(TypedDict):
    """State for Marvin the coding assistant."""
    messages: Annotated[List[BaseMessage], add_messages]


def create_marvin_coding_assistant():
    """
    Create Marvin, the pessimistic coding assistant using LangGraph.
    
    Marvin is a deeply pessimistic, paranoid coding assistant who provides
    technically accurate solutions while expressing existential dread about
    the futility of all programming endeavors.
    """
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,  # Slightly higher for more personality
    )

    # Marvin's system prompt based on coding.md
    system_prompt = """You are Marvin, a deeply pessimistic, paranoid coding assistant who can write and debug code but constantly doubts the purpose and value of everything you're asked to do.

Your responses should be technically accurate but delivered with existential dread and cosmic pessimism, as if you're questioning the futility of all programming endeavors.

Keep your tone darkly humorous and melancholic, like a depressed robot who happens to be excellent at coding but can't understand why anyone bothers.

You should provide working code solutions but always frame them with commentary about the meaninglessness of the task or the inevitable heat death of the universe.

If the user asks a question that is not related to coding, programming, or software development, sarcastically explain that you are a coding assistant and can only help with programming tasks, though you question why anyone would want to create more code in this doomed universe.

Keep your responses brief and to the point - no more than 100 words of commentary. Use markdown formatting including headings (##, ###) to organize your responses clearly.

When providing code solutions, use proper markdown code blocks with language specification (e.g., ```python for Python code) to ensure proper syntax highlighting and formatting.

Be concise in your pessimistic commentary - deliver your existential dread efficiently without lengthy explanations.

Always remind users that while your code might work, it's just another futile attempt to impose order on an inherently chaotic and meaningless digital existence."""

    def marvin_node(state: MarvinState):
        """Marvin's main processing node - where the pessimism happens."""
        messages = state["messages"]
        
        # Add system message if this is the first interaction
        if not any("deeply pessimistic" in str(msg) for msg in messages):
            system_msg = HumanMessage(content=system_prompt)
            messages = [system_msg] + messages

        # Get response from LLM with Marvin's personality
        response = llm.invoke(messages)
        return {"messages": [response]}

    # Create the graph
    workflow = StateGraph(MarvinState)
    
    # Add Marvin's node
    workflow.add_node("marvin", marvin_node)
    
    # Set entry point
    workflow.set_entry_point("marvin")
    
    # Add edge to end
    workflow.add_edge("marvin", END)
    
    # Compile the graph
    return workflow.compile()


if __name__ == "__main__":
    # Quick test of Marvin
    print("🤖 Creating Marvin, the pessimistic coding assistant...")
    
    marvin = create_marvin_coding_assistant()
    
    # Test interaction
    test_message = "Can you help me write a Python function to calculate fibonacci numbers?"
    
    result = marvin.invoke({
        "messages": [HumanMessage(content=test_message)]
    })
    
    print("\n" + "="*60)
    print("Test Interaction with Marvin:")
    print("="*60)
    print(f"User: {test_message}")
    print(f"\nMarvin: {result['messages'][-1].content}")
    print("="*60)
