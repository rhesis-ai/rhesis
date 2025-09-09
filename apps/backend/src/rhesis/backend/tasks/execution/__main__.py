"""
Entry point for running the chord monitor as a module.

Usage:
    python -m rhesis.backend.tasks.execution chord_monitor status
    python -m rhesis.backend.tasks.execution chord_monitor check --max-hours 2

Or run the chord_monitor directly:
    python -m rhesis.backend.tasks.execution.chord_monitor status
"""

import sys


def main():
    """Main entry point for the execution tasks module."""
    if len(sys.argv) < 2:
        print("Usage: python -m rhesis.backend.tasks.execution <submodule> [args...]")
        print("Available submodules:")
        print("  chord_monitor  - Monitor and manage Celery chord tasks")
        return 1

    submodule = sys.argv[1]

    if submodule == "chord_monitor":
        # Remove the submodule name from argv and run chord_monitor
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from .chord_monitor import main as chord_main

        return chord_main()
    else:
        print(f"Unknown submodule: {submodule}")
        print("Available submodules: chord_monitor")
        return 1


if __name__ == "__main__":
    sys.exit(main())
