#!/usr/bin/env python3
"""
Comprehensive Task Manager for Celery tasks.

This script provides comprehensive task management capabilities for Celery tasks,
including status checking, revoking, and cleanup operations. It automatically
loads environment variables from ../backend/.env and communicates with cloud workers.

Usage:
    python task_manager.py status <task_id>     # Check basic task status
    python task_manager.py revoke <task_id>     # Revoke a task (stop execution)
    python task_manager.py info <task_id>       # Get detailed task info with worker analysis
    python task_manager.py cleanup <task_id>    # Clean up task from result backend

Examples:
    python task_manager.py status 5221e37d-eb39-418c-8abd-0495161caf63
    python task_manager.py info 5221e37d-eb39-418c-8abd-0495161caf63
    python task_manager.py revoke 5221e37d-eb39-418c-8abd-0495161caf63
    python task_manager.py cleanup 5221e37d-eb39-418c-8abd-0495161caf63

Features:
- Automatic environment loading from ../backend/.env
- Real-time worker queue analysis (active, reserved, scheduled)
- Safe task revocation and cleanup
- Comprehensive error handling
- Works with cloud-deployed workers

Requirements:
- BROKER_URL and CELERY_RESULT_BACKEND in ../backend/.env
- Python environment with access to rhesis.backend.worker
"""

import os
import sys
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


def check_task_detailed(task_id: str):
    """Get detailed information about a task."""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        print(f"\n=== Detailed Task Info: {task_id} ===")
        print(f"Status: {result.status}")
        print(f"Ready: {result.ready()}")
        print(f"Successful: {result.successful() if result.ready() else 'N/A'}")
        print(f"Failed: {result.failed() if result.ready() else 'N/A'}")
        print(f"Date Done: {result.date_done}")
        print(f"Task Name: {result.name if hasattr(result, 'name') else 'Unknown'}")
        
        # Try to get more info
        try:
            print(f"Task Args: {result.args if hasattr(result, 'args') else 'Unknown'}")
            print(f"Task Kwargs: {result.kwargs if hasattr(result, 'kwargs') else 'Unknown'}")
        except:
            print("Task Args/Kwargs: Not available")
        
        if result.ready():
            if result.successful():
                print(f"Result: {result.result}")
            elif result.failed():
                print(f"Error: {result.result}")
                if result.traceback:
                    print(f"Traceback:\n{result.traceback}")
        
        # Check if task is in any worker queues
        inspector = celery_app.control.inspect()
        
        # Check active tasks
        active = inspector.active()
        found_active = False
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    if task['id'] == task_id:
                        print(f"\n✅ Task found in active queue on worker: {worker}")
                        print(f"   Task name: {task['name']}")
                        print(f"   Started: {task.get('time_start', 'Unknown')}")
                        found_active = True
        
        # Check reserved tasks
        reserved = inspector.reserved()
        found_reserved = False
        if reserved:
            for worker, tasks in reserved.items():
                for task in tasks:
                    if task['id'] == task_id:
                        print(f"\n📦 Task found in reserved queue on worker: {worker}")
                        print(f"   Task name: {task['name']}")
                        found_reserved = True
        
        # Check scheduled tasks
        scheduled = inspector.scheduled()
        found_scheduled = False
        if scheduled:
            for worker, tasks in scheduled.items():
                for task in tasks:
                    if task['request']['id'] == task_id:
                        print(f"\n⏰ Task found in scheduled queue on worker: {worker}")
                        print(f"   Task name: {task['request']['name']}")
                        print(f"   ETA: {task.get('eta', 'Unknown')}")
                        found_scheduled = True
        
        if not (found_active or found_reserved or found_scheduled):
            print("\n⚠️  Task not found in any worker queues")
            if result.status == 'PENDING':
                print("   This suggests the task might be:")
                print("   - Lost/expired from the queue")
                print("   - Stuck in the result backend")
                print("   - Never actually submitted")
        
        return result
        
    except Exception as e:
        print(f"❌ Error getting task info: {e}")
        return None


def revoke_task(task_id: str):
    """Revoke a task."""
    try:
        print(f"\n=== Revoking Task: {task_id} ===")
        
        # Try to revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        print("✅ Revoke command sent")
        
        # Check if the task was actually revoked
        result = AsyncResult(task_id, app=celery_app)
        print(f"Task status after revoke: {result.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error revoking task: {e}")
        return False


def cleanup_task(task_id: str):
    """Clean up task from result backend."""
    try:
        print(f"\n=== Cleaning Up Task: {task_id} ===")
        
        result = AsyncResult(task_id, app=celery_app)
        
        # Try to forget the task result
        result.forget()
        print("✅ Task result forgotten from backend")
        
        # Verify it's gone
        new_result = AsyncResult(task_id, app=celery_app)
        print(f"Task status after cleanup: {new_result.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning up task: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python task_manager.py status <task_id>")
        print("  python task_manager.py revoke <task_id>")
        print("  python task_manager.py info <task_id>")
        print("  python task_manager.py cleanup <task_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    task_id = sys.argv[2]
    
    print(f"Environment loaded - BROKER_URL: {bool(os.getenv('BROKER_URL'))}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if command == "status":
        result = AsyncResult(task_id, app=celery_app)
        print(f"\n=== Task Status: {task_id} ===")
        print(f"Status: {result.status}")
        print(f"Ready: {result.ready()}")
        
    elif command == "info":
        check_task_detailed(task_id)
        
    elif command == "revoke":
        revoke_task(task_id)
        
    elif command == "cleanup":
        cleanup_task(task_id)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main() 