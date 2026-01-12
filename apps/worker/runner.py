#!/usr/bin/env python3
"""
Task Runner for Debugging

A utility script to easily run any Celery task from the command line.
Provides context for organization_id and user_id automatically.

Usage:
    python runner.py task_name --arg1=value1 --arg2=value2 --org=org_id --user=user_id

Examples:
    python runner.py rhesis.backend.tasks.echo --message="Hello World" --org=org123 --user=user456
    python runner.py rhesis.backend.tasks.count_test_sets --org=org123 --user=user456
    python runner.py rhesis.backend.tasks.process_data --data='{"key":"value"}' --org=org123 --user=user456
    python runner.py rhesis.backend.tasks.execute_test_configuration --test_configuration_id="uuid-here" --org=org123 --user=user456
    
    # For sequential execution, use longer timeout:
    python runner.py rhesis.backend.tasks.execute_test_configuration --test_configuration_id="uuid-here" --org=org123 --user=user456 --timeout=300
"""

import argparse
import inspect
import json
import sys
import time
from typing import Optional

from rhesis.backend.tasks import task_launcher

# Import the Celery app and task_launcher
from rhesis.backend.worker import app as celery_app


class MockUser:
    """Mock user object for task_launcher to extract context from."""
    
    def __init__(self, user_id: str, organization_id: str):
        self.id = user_id
        self.organization_id = organization_id


def get_suggested_timeout(task_name: str, **kwargs) -> int:
    """
    Get suggested timeout based on task type and parameters.
    
    Sequential execution tasks need much longer timeouts than parallel tasks.
    """
    # Test configuration execution might need longer timeouts
    if 'execute_test_configuration' in task_name:
        try:
            # Try to check if we can detect sequential mode
            # This is a best-effort check - we can't always know without DB access
            test_config_id = kwargs.get('test_configuration_id')
            if test_config_id:
                # For test execution, suggest longer timeout
                # Sequential execution could take 5-10x longer than parallel
                return 300  # 5 minutes default for test execution
        except Exception:
            pass
    
    # Default timeout for other tasks
    return 30


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run a Celery task with parameters')
    parser.add_argument('task_name', help='Full name of the task to run')
    parser.add_argument('--org', dest='organization_id', required=True,
                        help='Organization ID for task context')
    parser.add_argument('--user', dest='user_id', required=True,
                        help='User ID for task context')
    parser.add_argument('--wait', dest='wait', action='store_true',
                        help='Wait for task to complete and show result')
    parser.add_argument('--timeout', dest='timeout', type=int, default=None,
                        help='Timeout in seconds when waiting for task (auto-detected if not provided)')
    parser.add_argument('--no-timeout', dest='no_timeout', action='store_true',
                        help='Wait indefinitely for task to complete (no timeout)')
    
    # Parse known args for task parameters and get any unknown args
    args, extra_args = parser.parse_known_args()
    
    # Process extra arguments (--key=value format)
    task_kwargs = {}
    for arg in extra_args:
        if arg.startswith('--'):
            parts = arg[2:].split('=', 1)
            if len(parts) == 2:
                key, value = parts
                # Try to parse JSON values (for objects, arrays, booleans, etc.)
                try:
                    task_kwargs[key] = json.loads(value)
                except json.JSONDecodeError:
                    task_kwargs[key] = value
    
    return args, task_kwargs


def get_task(task_name: str):
    """Get a task by name from the Celery app."""
    try:
        return celery_app.tasks[task_name]
    except KeyError:
        print(f"Error: Task '{task_name}' not found!")
        print("\nAvailable tasks:")
        for name in sorted(task for task in celery_app.tasks.keys() 
                           if not task.startswith('celery.')):
            print(f"  - {name}")
        sys.exit(1)


def is_bound_task(task):
    """Check if a task is bound (has a 'self' parameter)."""
    # Get the __call__ method's signature
    sig = inspect.signature(task.__call__)
    # Check if the first parameter is 'self'
    params = list(sig.parameters.keys())
    # Skip the first parameter if it's 'self'
    return params and params[0] == 'self'


def run_task(task_name: str, organization_id: str, user_id: str, 
             wait: bool = False, timeout: Optional[int] = None, 
             no_timeout: bool = False, **kwargs):
    """Run a task with the given arguments and context."""
    task = get_task(task_name)
    
    # Auto-detect timeout if not provided
    if timeout is None and not no_timeout:
        timeout = get_suggested_timeout(task_name, **kwargs)
        print(f"Auto-detected timeout: {timeout} seconds")
    elif no_timeout:
        timeout = None
        print("Running with no timeout (will wait indefinitely)")
    
    # Create a mock user with context
    mock_user = MockUser(user_id=user_id, organization_id=organization_id)
    
    # Print details about the task being run
    print(f"\nRunning task: {task_name}")
    print(f"Context: organization_id={organization_id}, user_id={user_id}")
    print(f"Arguments: {json.dumps(kwargs, indent=2, default=str)}")
    
    # Special guidance for test execution tasks
    if 'execute_test_configuration' in task_name:
        print("\n📋 Test Execution Task Detected:")
        print("   • Sequential execution will take longer than parallel")
        print("   • Use --timeout=300 or higher for sequential execution")
        print("   • Use --no-timeout to wait indefinitely")
        print("   • Monitor logs for execution progress")
    
    # Run the task
    try:
        # For tasks with 'self' parameter, we need to apply the task differently
        if is_bound_task(task):
            print("Detected bound task (with 'self' parameter)")
            # Use apply_async instead of direct call through task_launcher
            result = task.apply_async(
                kwargs=kwargs,
                headers={'organization_id': organization_id, 'user_id': user_id}
            )
        else:
            # Use the original task_launcher for non-bound tasks
            result = task_launcher(task, current_user=mock_user, **kwargs)
            
        print("\nTask submitted successfully!")
        print(f"Task ID: {result.id}")
        
        if wait:
            print("\nWaiting for task to complete...")
            if timeout:
                print(f"Timeout: {timeout} seconds")
            else:
                print("No timeout set - will wait indefinitely")
                
            start_time = time.time()
            
            try:
                result.get(timeout=timeout, propagate=False)
                elapsed = time.time() - start_time
                print(f"Task completed in {elapsed:.2f} seconds")
                
                if result.successful():
                    print("\n✅ Task completed successfully!")
                    print("Result:")
                    print(json.dumps(result.result, indent=2, default=str))
                elif result.failed():
                    print("\n❌ Task failed with error:")
                    print(result.traceback)
                else:
                    print(f"\n⚠️  Unexpected status: {result.status}")
                    
            except Exception as e:
                if "timed out" in str(e).lower():
                    elapsed = time.time() - start_time
                    print(f"\n⏰ Task timed out after {elapsed:.2f} seconds")
                    print("\n💡 Suggestions:")
                    print("   • Use --timeout=600 for longer timeout (10 minutes)")
                    print("   • Use --no-timeout to wait indefinitely")
                    print("   • Check if execution mode is Sequential (takes longer)")
                    print("   • Monitor task logs for progress")
                    print(f"   • Task ID: {result.id} (still running in background)")
                else:
                    print(f"\n❌ Error waiting for task: {e}")
            
    except Exception as e:
        print(f"\n❌ Error launching task: {e}")
        sys.exit(1)


if __name__ == "__main__":
    args, task_kwargs = parse_arguments()
    run_task(
        task_name=args.task_name,
        organization_id=args.organization_id,
        user_id=args.user_id,
        wait=args.wait,
        timeout=args.timeout,
        no_timeout=args.no_timeout,
        **task_kwargs
    )
