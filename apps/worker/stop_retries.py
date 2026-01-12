#!/usr/bin/env python3
"""
Script to stop stuck retry loops for Celery tasks.

This specialized script is designed to handle tasks stuck in infinite retry loops.
It uses multiple aggressive methods to ensure tasks are completely stopped and
provides comprehensive analysis of retry status.

Usage:
    python stop_retries.py <task_id>           # Force stop a specific task's retry loop
    python stop_retries.py --all-retries       # List all tasks currently scheduled for retry
    python stop_retries.py --check <task_id>   # Check if specific task is in retry loop

Examples:
    python stop_retries.py 5221e37d-eb39-418c-8abd-0495161caf63
    python stop_retries.py --check 5221e37d-eb39-418c-8abd-0495161caf63
    python stop_retries.py --all-retries

Methods Used to Stop Tasks:
1. Revoke with SIGKILL (terminates running instances)
2. Revoke without terminate (prevents new executions)
3. Forget from result backend (clears stored results)
4. Verification and status checking

Features:
- Multi-method aggressive task stopping
- Retry loop detection across all worker queues
- Scheduled task analysis (future retry attempts)
- Comprehensive cleanup verification
- Safe operation with error handling

Use Cases:
- Long-running tasks stuck in retry loops
- Failed tasks consuming worker resources
- System performance issues due to retrying tasks
- Pre-deployment cleanup of problematic tasks

Requirements:
- BROKER_URL and CELERY_RESULT_BACKEND in ../backend/.env
- Python environment with access to rhesis.backend.worker
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env from apps/backend directory
backend_dir = Path(__file__).parent.parent / "backend"
env_file = backend_dir / ".env"

if env_file.exists():
    load_dotenv(env_file)

from celery.result import AsyncResult

from rhesis.backend.worker import app as celery_app


def force_stop_task(task_id: str):
    """Aggressively stop a task using multiple methods."""
    print(f"\n=== Force Stopping Task: {task_id} ===")
    
    try:
        # Method 1: Revoke with terminate=True (kills running instances)
        print("1. Sending revoke command with terminate=True...")
        celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
        print("   ✅ Revoke with SIGKILL sent")
        
        # Method 2: Revoke with terminate=False (prevents new executions)
        print("2. Sending revoke command to prevent new executions...")
        celery_app.control.revoke(task_id, terminate=False)
        print("   ✅ Revoke to prevent new executions sent")
        
        # Method 3: Forget the result to clear from backend
        print("3. Clearing task from result backend...")
        result = AsyncResult(task_id, app=celery_app)
        result.forget()
        print("   ✅ Task forgotten from result backend")
        
        # Wait a moment for commands to propagate
        print("4. Waiting for commands to propagate...")
        time.sleep(2)
        
        # Method 4: Check final status
        print("5. Checking final status...")
        final_result = AsyncResult(task_id, app=celery_app)
        print(f"   Final status: {final_result.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error force stopping task: {e}")
        return False


def check_task_retry_status(task_id: str):
    """Check if a task is currently in a retry loop."""
    print(f"\n=== Checking Retry Status: {task_id} ===")
    
    try:
        inspector = celery_app.control.inspect()
        
        # Check active tasks
        active = inspector.active()
        found_active = False
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    if task['id'] == task_id:
                        print(f"🔄 Task ACTIVE on worker: {worker}")
                        print(f"   Task name: {task['name']}")
                        print(f"   Started: {task.get('time_start', 'Unknown')}")
                        found_active = True
        
        # Check reserved tasks (waiting to run)
        reserved = inspector.reserved()
        found_reserved = False
        if reserved:
            for worker, tasks in reserved.items():
                for task in tasks:
                    if task['id'] == task_id:
                        print(f"📦 Task RESERVED on worker: {worker}")
                        print(f"   Task name: {task['name']}")
                        found_reserved = True
        
        # Check scheduled tasks (retries scheduled for future)
        scheduled = inspector.scheduled()
        found_scheduled = False
        if scheduled:
            for worker, tasks in scheduled.items():
                for task in tasks:
                    if task['request']['id'] == task_id:
                        print(f"⏰ Task SCHEDULED for retry on worker: {worker}")
                        print(f"   Task name: {task['request']['name']}")
                        print(f"   ETA: {task.get('eta', 'Unknown')}")
                        found_scheduled = True
        
        if found_active or found_reserved or found_scheduled:
            print("\n⚠️  TASK IS STILL IN RETRY LOOP!")
            return True
        else:
            print("\n✅ Task is not found in any worker queues")
            
            # Also check result backend status
            result = AsyncResult(task_id, app=celery_app)
            print(f"Result backend status: {result.status}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking retry status: {e}")
        return None


def list_all_retrying_tasks():
    """Find all tasks that might be stuck in retry loops."""
    print("\n=== Finding All Retrying Tasks ===")
    
    try:
        inspector = celery_app.control.inspect()
        
        retrying_tasks = []
        
        # Check scheduled tasks (these are often retries)
        scheduled = inspector.scheduled()
        if scheduled:
            for worker, tasks in scheduled.items():
                for task in tasks:
                    task_info = {
                        'id': task['request']['id'],
                        'name': task['request']['name'],
                        'worker': worker,
                        'eta': task.get('eta', 'Unknown'),
                        'type': 'scheduled'
                    }
                    retrying_tasks.append(task_info)
        
        if retrying_tasks:
            print(f"Found {len(retrying_tasks)} potentially retrying tasks:")
            for task in retrying_tasks:
                print(f"  - {task['name']} [{task['id']}] on {task['worker']}")
                print(f"    ETA: {task['eta']}")
        else:
            print("No retrying tasks found")
            
        return retrying_tasks
        
    except Exception as e:
        print(f"❌ Error listing retrying tasks: {e}")
        return []


def main():
    print(f"Environment loaded - BROKER_URL: {bool(os.getenv('BROKER_URL'))}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python stop_retries.py <task_id>           # Stop specific task")
        print("  python stop_retries.py --all-retries       # Show all retrying tasks") 
        print("  python stop_retries.py --check <task_id>   # Check if task is still retrying")
        sys.exit(1)
    
    if sys.argv[1] == "--all-retries":
        list_all_retrying_tasks()
        
    elif sys.argv[1] == "--check":
        if len(sys.argv) < 3:
            print("Error: --check requires a task_id")
            sys.exit(1)
        task_id = sys.argv[2]
        check_task_retry_status(task_id)
        
    else:
        # Assume it's a task_id to stop
        task_id = sys.argv[1]
        
        # First check if it's retrying
        print("Checking current retry status...")
        is_retrying = check_task_retry_status(task_id)
        
        if is_retrying:
            print("\nTask is still retrying. Attempting to force stop...")
            force_stop_task(task_id)
            
            # Check again after stopping
            print("\nRechecking status after stop attempt...")
            time.sleep(3)
            final_status = check_task_retry_status(task_id)
            
            if not final_status:
                print("\n🎉 SUCCESS: Task retry loop has been stopped!")
            else:
                print("\n⚠️  Task may still be retrying. You may need to restart workers.")
        else:
            print("\nTask is not currently retrying.")


if __name__ == "__main__":
    main() 