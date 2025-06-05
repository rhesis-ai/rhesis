"""
Chord monitoring utilities to track and manage chord executions.

Usage:
    python -m rhesis.backend.tasks.execution.chord_monitor status
    python -m rhesis.backend.tasks.execution.chord_monitor check --max-hours 2
    python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 1 --dry-run
    python -m rhesis.backend.tasks.execution.chord_monitor clean --force
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

from celery.result import AsyncResult, GroupResult
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.worker import app


def get_chord_status(chord_id: str) -> Dict[str, Any]:
    """
    Get the status of a chord by its ID.
    
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
            if hasattr(result, 'parent') and result.parent:
                parent_result = AsyncResult(result.parent, app=app)
                if isinstance(parent_result, GroupResult):
                    subtasks = []
                    for subtask_result in parent_result.results:
                        subtasks.append({
                            "id": subtask_result.id,
                            "status": subtask_result.status,
                            "ready": subtask_result.ready(),
                            "successful": subtask_result.successful() if subtask_result.ready() else None,
                            "failed": subtask_result.failed() if subtask_result.ready() else None,
                        })
                    status_info["subtasks"] = subtasks
                    status_info["total_subtasks"] = len(subtasks)
                    status_info["completed_subtasks"] = sum(1 for st in subtasks if st["ready"])
                    status_info["failed_subtasks"] = sum(1 for st in subtasks if st["failed"])
        except Exception as e:
            logger.warning(f"Could not get group information for chord {chord_id}: {e}")
            
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting chord status for {chord_id}: {e}")
        return {
            "chord_id": chord_id,
            "error": str(e),
            "status": "error"
        }


def get_active_chord_unlocks() -> List[Dict[str, Any]]:
    """
    Get information about active chord_unlock tasks.
    
    Returns:
        List of active chord unlock tasks
    """
    try:
        # Get active tasks from all workers
        active_tasks = app.control.inspect().active()
        
        chord_unlocks = []
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if task.get('name') == 'celery.chord_unlock':
                        chord_unlocks.append({
                            "worker": worker,
                            "task_id": task.get('id'),
                            "name": task.get('name'),
                            "args": task.get('args', []),
                            "kwargs": task.get('kwargs', {}),
                            "time_start": task.get('time_start'),
                            "acknowledged": task.get('acknowledged'),
                            "delivery_info": task.get('delivery_info', {}),
                        })
        
        return chord_unlocks
        
    except Exception as e:
        logger.error(f"Error getting active chord unlocks: {e}")
        return []


def check_stuck_chords(max_runtime_hours: int = 1) -> List[Dict[str, Any]]:
    """
    Check for chord_unlock tasks that have been running too long.
    
    Args:
        max_runtime_hours: Maximum runtime in hours before considering a chord stuck
        
    Returns:
        List of potentially stuck chord tasks
    """
    stuck_chords = []
    chord_unlocks = get_active_chord_unlocks()
    
    cutoff_time = datetime.utcnow() - timedelta(hours=max_runtime_hours)
    
    for chord in chord_unlocks:
        time_start = chord.get('time_start')
        if time_start:
            try:
                start_time = datetime.fromtimestamp(time_start)
                if start_time < cutoff_time:
                    chord['runtime_hours'] = (datetime.utcnow() - start_time).total_seconds() / 3600
                    stuck_chords.append(chord)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse start time for chord {chord.get('task_id')}: {e}")
    
    return stuck_chords


def revoke_stuck_chords(max_runtime_hours: int = 1, dry_run: bool = True) -> Dict[str, Any]:
    """
    Revoke chord_unlock tasks that have been running too long.
    
    Args:
        max_runtime_hours: Maximum runtime in hours before revoking
        dry_run: If True, only report what would be revoked without actually doing it
        
    Returns:
        Dictionary with revocation results
    """
    stuck_chords = check_stuck_chords(max_runtime_hours)
    
    results = {
        "dry_run": dry_run,
        "found_stuck_chords": len(stuck_chords),
        "revoked_chords": [],
        "errors": []
    }
    
    if not stuck_chords:
        logger.info("No stuck chords found")
        return results
    
    logger.warning(f"Found {len(stuck_chords)} potentially stuck chord(s)")
    
    for chord in stuck_chords:
        task_id = chord.get('task_id')
        runtime_hours = chord.get('runtime_hours', 0)
        
        logger.warning(f"Chord {task_id} has been running for {runtime_hours:.2f} hours")
        
        if not dry_run:
            try:
                app.control.revoke(task_id, terminate=True)
                results["revoked_chords"].append({
                    "task_id": task_id,
                    "runtime_hours": runtime_hours
                })
                logger.info(f"Revoked stuck chord {task_id}")
            except Exception as e:
                error_msg = f"Failed to revoke chord {task_id}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        else:
            results["revoked_chords"].append({
                "task_id": task_id,
                "runtime_hours": runtime_hours,
                "action": "would_revoke"
            })
    
    return results


def print_chord_summary():
    """Print a summary of chord status for debugging."""
    print("\n=== Chord Status Summary ===")
    
    # Check for active chord unlocks
    chord_unlocks = get_active_chord_unlocks()
    print(f"Active chord_unlock tasks: {len(chord_unlocks)}")
    
    for chord in chord_unlocks:
        task_id = chord.get('task_id', 'unknown')
        worker = chord.get('worker', 'unknown')
        time_start = chord.get('time_start')
        
        if time_start:
            start_time = datetime.fromtimestamp(time_start)
            runtime = (datetime.utcnow() - start_time).total_seconds() / 60  # minutes
            print(f"  - {task_id} on {worker} (running {runtime:.1f} minutes)")
        else:
            print(f"  - {task_id} on {worker} (start time unknown)")
    
    # Check for stuck chords
    stuck_chords = check_stuck_chords(max_runtime_hours=0.5)  # 30 minutes
    if stuck_chords:
        print(f"\nWARNING: Found {len(stuck_chords)} chord(s) running >30 minutes:")
        for chord in stuck_chords:
            task_id = chord.get('task_id', 'unknown')
            runtime_hours = chord.get('runtime_hours', 0)
            print(f"  - {task_id} ({runtime_hours:.2f} hours)")
    else:
        print("\nNo stuck chords detected")


def purge_all_tasks() -> Dict[str, Any]:
    """
    Purge all tasks from all queues.
    
    Returns:
        Dictionary with purge results
    """
    try:
        result = app.control.purge()
        return {
            "success": True,
            "message": "All tasks purged successfully",
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to purge tasks"
        }


def cmd_status(args):
    """Command: Show chord status summary."""
    print_chord_summary()


def cmd_check(args):
    """Command: Check for stuck chords."""
    stuck_chords = check_stuck_chords(max_runtime_hours=args.max_hours)
    
    if not stuck_chords:
        print(f"✅ No stuck chords found (checked for tasks running >{args.max_hours} hours)")
        return 0
    
    print(f"⚠️  Found {len(stuck_chords)} stuck chord(s) running >{args.max_hours} hours:")
    for chord in stuck_chords:
        task_id = chord.get('task_id', 'unknown')
        runtime_hours = chord.get('runtime_hours', 0)
        worker = chord.get('worker', 'unknown')
        print(f"   - {task_id} on {worker} ({runtime_hours:.2f} hours)")
    
    if args.json:
        print("\nJSON output:")
        print(json.dumps(stuck_chords, indent=2))
    
    return 1  # Exit code 1 indicates stuck chords found


def cmd_revoke(args):
    """Command: Revoke stuck chords."""
    results = revoke_stuck_chords(
        max_runtime_hours=args.max_hours,
        dry_run=args.dry_run
    )
    
    if results["found_stuck_chords"] == 0:
        print(f"✅ No stuck chords found (checked for tasks running >{args.max_hours} hours)")
        return 0
    
    if args.dry_run:
        print(f"🔍 DRY RUN: Would revoke {len(results['revoked_chords'])} stuck chord(s):")
    else:
        print(f"⚡ Revoked {len(results['revoked_chords'])} stuck chord(s):")
    
    for chord in results["revoked_chords"]:
        task_id = chord.get('task_id', 'unknown')
        runtime_hours = chord.get('runtime_hours', 0)
        action = "WOULD REVOKE" if args.dry_run else "REVOKED"
        print(f"   - {action}: {task_id} ({runtime_hours:.2f} hours)")
    
    if results["errors"]:
        print(f"\n❌ Errors occurred:")
        for error in results["errors"]:
            print(f"   - {error}")
        return 1
    
    if args.json:
        print("\nJSON output:")
        print(json.dumps(results, indent=2))
    
    return 0


def cmd_clean(args):
    """Command: Purge all tasks from queues."""
    if not args.force:
        print("⚠️  This will purge ALL tasks from ALL queues!")
        print("   Use --force to confirm this action.")
        return 1
    
    print("🗑️  Purging all tasks from queues...")
    results = purge_all_tasks()
    
    if results["success"]:
        print("✅ All tasks purged successfully")
        if args.json:
            print(json.dumps(results, indent=2))
        return 0
    else:
        print(f"❌ Failed to purge tasks: {results['error']}")
        return 1


def cmd_inspect(args):
    """Command: Inspect a specific chord by ID."""
    if not args.chord_id:
        print("❌ Chord ID is required for inspect command")
        return 1
    
    status = get_chord_status(args.chord_id)
    
    if "error" in status:
        print(f"❌ Error getting chord status: {status['error']}")
        return 1
    
    print(f"\n=== Chord {args.chord_id} ===")
    print(f"Status: {status['status']}")
    print(f"Ready: {status['ready']}")
    
    if status['ready']:
        print(f"Successful: {status['successful']}")
        print(f"Failed: {status['failed']}")
        if status['date_done']:
            print(f"Completed: {status['date_done']}")
    
    if status.get('subtasks'):
        print(f"\nSubtasks: {status['total_subtasks']}")
        print(f"Completed: {status['completed_subtasks']}")
        print(f"Failed: {status['failed_subtasks']}")
        
        if args.verbose:
            print("\nSubtask details:")
            for subtask in status['subtasks']:
                print(f"  - {subtask['id']}: {subtask['status']}")
    
    if status.get('traceback') and args.verbose:
        print(f"\nTraceback:\n{status['traceback']}")
    
    if args.json:
        print("\nJSON output:")
        print(json.dumps(status, indent=2))
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor and manage Celery chord tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                          # Show chord status summary
  %(prog)s check --max-hours 2             # Check for chords running >2 hours
  %(prog)s revoke --max-hours 1 --dry-run  # Show what would be revoked
  %(prog)s revoke --max-hours 1            # Actually revoke stuck chords
  %(prog)s clean --force                   # Purge all tasks (dangerous!)
  %(prog)s inspect <chord-id> --verbose    # Inspect specific chord
        """
    )
    
    parser.add_argument(
        '--json', 
        action='store_true',
        help='Output results in JSON format'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show chord status summary')
    status_parser.set_defaults(func=cmd_status)
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check for stuck chords')
    check_parser.add_argument(
        '--max-hours', 
        type=float, 
        default=1.0,
        help='Maximum runtime in hours before considering a chord stuck (default: 1.0)'
    )
    check_parser.set_defaults(func=cmd_check)
    
    # Revoke command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke stuck chords')
    revoke_parser.add_argument(
        '--max-hours', 
        type=float, 
        default=1.0,
        help='Maximum runtime in hours before revoking (default: 1.0)'
    )
    revoke_parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be revoked without actually doing it'
    )
    revoke_parser.set_defaults(func=cmd_revoke)
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Purge all tasks from queues')
    clean_parser.add_argument(
        '--force', 
        action='store_true',
        help='Actually purge tasks (required for safety)'
    )
    clean_parser.set_defaults(func=cmd_clean)
    
    # Inspect command
    inspect_parser = subparsers.add_parser('inspect', help='Inspect a specific chord')
    inspect_parser.add_argument(
        'chord_id',
        help='The chord task ID to inspect'
    )
    inspect_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed information including subtasks and tracebacks'
    )
    inspect_parser.set_defaults(func=cmd_inspect)
    
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