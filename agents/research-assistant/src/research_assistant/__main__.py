"""Entry point for running the Research Assistant as a module.

Usage:
    python -m research_assistant
    python -m research_assistant --host 0.0.0.0 --port 8888
"""

import sys


def main():
    """Run the Research Assistant FastAPI server."""
    import uvicorn

    # Default values
    host = "0.0.0.0"
    port = 8888

    # Simple CLI argument parsing
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1

    uvicorn.run(
        "research_assistant.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
