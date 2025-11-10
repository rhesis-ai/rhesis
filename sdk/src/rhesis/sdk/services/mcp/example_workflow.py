"""
Example: Interactive MCP workflow (Search → User Selects → Extract)

This demonstrates how the frontend workflow would work:
1. Search for pages matching a query
2. Display results to user
3. User manually selects which pages to extract
4. Extract full content from selected pages

The workflow is server-agnostic and works with any MCP server (Notion, GitHub, Slack, etc.)
"""

import os

from rhesis.sdk.models import get_model
from rhesis.sdk.services.mcp import (
    MCPClientManager,
    MCPExtractAgent,
    MCPSearchAgent,
)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system environment variables


def main():
    """Interactive example simulating frontend workflow."""
    print("=" * 70)
    print("Interactive MCP Workflow: Search → Select → Extract")
    print("=" * 70)

    # Initialize LLM
    llm = get_model(
        provider="gemini",
        model_name="gemini-2.0-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    # Create MCP client for Notion
    manager = MCPClientManager()
    mcp_client = manager.create_client("notionApi")

    # ========================================================================
    # Phase 1: Search for pages
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 1: SEARCH")
    print("=" * 70)

    # Get search query from user
    search_query = input("\nEnter your search query (e.g., 'Find PRD documents'): ").strip()
    if not search_query:
        search_query = "Find PRD documents"  # Default
        print(f"Using default: {search_query}")

    search_agent = MCPSearchAgent(
        llm=llm,
        mcp_client=mcp_client,
        max_iterations=10,
        verbose=True,  # Enable verbose mode to see debugging
    )

    print(f"\n🔍 Searching for: {search_query}")
    search_result = search_agent.run(search_query)

    # Display search results
    if not search_result.success:
        print("\n❌ Search failed")
        print(f"Error: {search_result.error}")
        return

    print("\n" + "=" * 70)
    print(f"📄 FOUND {search_result.total_found} PAGE(S)")
    print("=" * 70)

    if search_result.total_found == 0:
        print("\nNo pages found. Try a different search query.")
        return

    # Display results with selection numbers
    for i, page in enumerate(search_result.pages, 1):
        print(f"\n[{i}] {page.title or 'Untitled'}")
        print(f"    ID: {page.page_id}")
        if page.url:
            print(f"    URL: {page.url}")
        if page.last_edited:
            print(f"    Last edited: {page.last_edited}")
        if page.excerpt:
            excerpt = page.excerpt[:150] + "..." if len(page.excerpt) > 150 else page.excerpt
            print(f"    Preview: {excerpt}")

    # ========================================================================
    # Phase 2: User selects pages
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: SELECT PAGES")
    print("=" * 70)

    # Get user selection
    while True:
        selection = input(
            "\nEnter page numbers to extract (comma-separated, e.g., '1,3' or 'all'): "
        ).strip()

        if selection.lower() == "all":
            selected_indices = list(range(len(search_result.pages)))
            break
        elif selection.lower() in ["none", "exit", "quit", ""]:
            print("No pages selected. Exiting.")
            return
        else:
            try:
                # Parse comma-separated numbers
                selected_indices = [
                    int(num.strip()) - 1  # Convert to 0-indexed
                    for num in selection.split(",")
                    if num.strip()
                ]
                # Validate indices
                if all(0 <= idx < len(search_result.pages) for idx in selected_indices):
                    break
                else:
                    max_num = len(search_result.pages)
                    print(f"❌ Invalid selection. Please enter numbers between 1 and {max_num}")
            except ValueError:
                print("❌ Invalid input. Please enter numbers separated by commas.")

    selected_pages = [search_result.pages[i] for i in selected_indices]
    selected_ids = [p.page_id for p in selected_pages]

    print(f"\n✓ Selected {len(selected_pages)} page(s):")
    for page in selected_pages:
        print(f"  • {page.title or 'Untitled'}")

    # ========================================================================
    # Phase 3: Extract content from selected pages
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: EXTRACT CONTENT")
    print("=" * 70)

    print(f"\n📥 Extracting content from {len(selected_pages)} page(s)...")

    extract_agent = MCPExtractAgent(
        llm=llm,
        mcp_client=mcp_client,
        max_iterations=15,
        verbose=False,
    )

    extract_result = extract_agent.run(
        page_ids=selected_ids,
        context={"purpose": "Import as sources", "query": search_query},
    )

    # Display extraction results
    if not extract_result.success:
        print("\n❌ Extraction failed")
        print(f"Error: {extract_result.error}")
        return

    print("\n" + "=" * 70)
    print(f"✅ EXTRACTED {extract_result.total_extracted} PAGE(S)")
    print("=" * 70)

    for i, page in enumerate(extract_result.pages, 1):
        print(f"\n[{i}] {page.title or 'Untitled'}")
        print(f"    Source: {page.source_type}")
        print(f"    Content length: {len(page.content):,} characters")
        print(f"    URL: {page.metadata.url or 'N/A'}")

        # Show content preview
        if page.content:
            print("\n    Content preview:")
            print("    " + "-" * 66)
            preview = page.content[:200].replace("\n", "\n    ")
            print(f"    {preview}...")
            print("    " + "-" * 66)

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("🎉 WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"✓ Searched and found {search_result.total_found} pages")
    print(f"✓ User selected {len(selected_pages)} pages")
    print(f"✓ Successfully extracted {extract_result.total_extracted} pages")
    total_iterations = search_result.iterations_used + extract_result.iterations_used
    print(f"✓ Total LLM iterations: {total_iterations}")
    print("\n💡 Next steps:")
    print("  • Save extracted content as Source documents in the database")
    print("  • Use content for RAG, generation, or analysis")
    print("  • Repeat workflow with different queries")


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
        # Run the main workflow
        main()
