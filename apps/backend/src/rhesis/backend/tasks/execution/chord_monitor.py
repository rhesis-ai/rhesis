"""
Redis Chord monitoring utilities for tracking and managing chord executions.

Usage:
    python -m rhesis.backend.tasks.execution.chord_monitor status
    python -m rhesis.backend.tasks.execution.chord_monitor check --chord-id <id>
    python -m rhesis.backend.tasks.execution.chord_monitor clean --force
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict

from celery.result import AsyncResult, GroupResult

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.worker import app


def get_chord_status(chord_id: str) -> Dict[str, Any]:
    """
    Get the status of a Redis chord by its ID.

    Args:
        chord_id: The chord task ID

    Returns:
        Dictionary with chord status information
    """
    try:
        result = AsyncResult(chord_id, app=app)

        status_info = {
            "chord_id": chord_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
            "date_done": result.date_done.isoformat() if result.date_done else None,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
        }

        # Try to get group information if this is a chord
        try:
            if hasattr(result, "parent") and result.parent:
                parent_result = AsyncResult(result.parent, app=app)
                if isinstance(parent_result, GroupResult):
                    subtasks = []
                    for subtask_result in parent_result.results:
                        subtasks.append(
                            {
                                "id": subtask_result.id,
                                "status": subtask_result.status,
                                "ready": subtask_result.ready(),
                                "successful": subtask_result.successful()
                                if subtask_result.ready()
                                else None,
                                "failed": subtask_result.failed()
                                if subtask_result.ready()
                                else None,
                            }
                        )
                    status_info["subtasks"] = subtasks
                    status_info["total_subtasks"] = len(subtasks)
                    status_info["completed_subtasks"] = sum(1 for st in subtasks if st["ready"])
                    status_info["failed_subtasks"] = sum(1 for st in subtasks if st["failed"])
        except Exception as e:
            logger.warning(f"Could not get group information for chord {chord_id}: {e}")

        return status_info

    except Exception as e:
        logger.error(f"Error getting chord status for {chord_id}: {e}")
        return {"chord_id": chord_id, "error": str(e), "status": "error"}


def get_chord_summary() -> Dict[str, Any]:
    """Get a summary of chord activity from Redis."""
    try:
        # Get Redis connection info
        redis_info = {
            "broker_url": app.conf.broker_url,
            "result_backend": app.conf.result_backend,
            "redis_max_connections": app.conf.redis_max_connections,
        }

        # Get worker stats
        worker_stats = app.control.inspect().stats()
        active_tasks = app.control.inspect().active()

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "redis_config": redis_info,
            "workers": len(worker_stats) if worker_stats else 0,
            "total_active_tasks": 0,
            "chord_tasks": 0,
        }

        if active_tasks:
            for worker, tasks in active_tasks.items():
                summary["total_active_tasks"] += len(tasks)
                # Count chord-related tasks
                for task in tasks:
                    if "chord" in task.get("name", "").lower():
                        summary["chord_tasks"] += 1

        return summary

    except Exception as e:
        logger.error(f"Error getting chord summary: {e}")
        return {"error": str(e)}


def purge_all_tasks() -> Dict[str, Any]:
    """Purge all tasks from Redis queues."""
    try:
        result = app.control.purge()
        return {
            "success": True,
            "message": "All tasks purged successfully from Redis",
            "result": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Failed to purge tasks from Redis"}


def cmd_status(args):
    """Command: Show Redis chord status summary."""
    summary = get_chord_summary()

    print("\n=== Redis Chord Status Summary ===")
    if "error" in summary:
        print(f"❌ Error: {summary['error']}")
        return 1

    print(f"Workers: {summary['workers']}")
    print(f"Active tasks: {summary['total_active_tasks']}")
    print(f"Chord tasks: {summary['chord_tasks']}")
    print(f"Redis broker: {summary['redis_config']['broker_url']}")
    print(f"Redis result backend: {summary['redis_config']['result_backend']}")

    if args.json:
        print("\nJSON output:")
        print(json.dumps(summary, indent=2))

    return 0


def cmd_check(args):
    """Command: Check specific chord status."""
    if not args.chord_id:
        print("❌ Chord ID is required for check command")
        return 1

    status = get_chord_status(args.chord_id)

    if "error" in status:
        print(f"❌ Error getting chord status: {status['error']}")
        return 1

    print(f"\n=== Chord {args.chord_id} ===")
    print(f"Status: {status['status']}")
    print(f"Ready: {status['ready']}")

    if status["ready"]:
        print(f"Successful: {status['successful']}")
        print(f"Failed: {status['failed']}")
        if status["date_done"]:
            print(f"Completed: {status['date_done']}")

    if status.get("subtasks"):
        print(f"\nSubtasks: {status['total_subtasks']}")
        print(f"Completed: {status['completed_subtasks']}")
        print(f"Failed: {status['failed_subtasks']}")

        if args.verbose:
            print("\nSubtask details:")
            for subtask in status["subtasks"]:
                print(f"  - {subtask['id']}: {subtask['status']}")

    if status.get("traceback") and args.verbose:
        print(f"\nTraceback:\n{status['traceback']}")

    if args.json:
        print("\nJSON output:")
        print(json.dumps(status, indent=2))

    return 0


def cmd_clean(args):
    """Command: Purge all tasks from Redis queues."""
    if not args.force:
        print("⚠️  This will purge ALL tasks from Redis queues!")
        print("   Use --force to confirm this action.")
        return 1

    print("🗑️  Purging all tasks from Redis...")
    results = purge_all_tasks()

    if results["success"]:
        print("✅ All tasks purged successfully from Redis")
        if args.json:
            print(json.dumps(results, indent=2))
        return 0
    else:
        print(f"❌ Failed to purge tasks: {results['error']}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor and manage Redis Celery chord tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                          # Show Redis chord status summary
  %(prog)s check --chord-id <id>           # Check specific chord status
  %(prog)s clean --force                   # Purge all tasks (dangerous!)
        """,
    )

    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show Redis chord status summary")
    status_parser.set_defaults(func=cmd_status)

    # Check command
    check_parser = subparsers.add_parser("check", help="Check specific chord status")
    check_parser.add_argument("--chord-id", required=True, help="The chord task ID to check")
    check_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information including subtasks and tracebacks",
    )
    check_parser.set_defaults(func=cmd_check)

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Purge all tasks from Redis queues")
    clean_parser.add_argument(
        "--force", action="store_true", help="Actually purge tasks (required for safety)"
    )
    clean_parser.set_defaults(func=cmd_clean)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
