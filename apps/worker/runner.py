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
"""

import argparse
import json
import sys
import time
import inspect
from typing import Any, Dict, Optional

# Import the Celery app and task_launcher
from rhesis.backend.worker import app as celery_app
from rhesis.backend.tasks import task_launcher


class MockUser:
    """Mock user object for task_launcher to extract context from."""
    
    def __init__(self, user_id: str, organization_id: str):
        self.id = user_id
        self.organization_id = organization_id


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
    parser.add_argument('--timeout', dest='timeout', type=int, default=30,
                        help='Timeout in seconds when waiting for task (default: 30)')
    
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
             wait: bool = False, timeout: int = 30, **kwargs):
    """Run a task with the given arguments and context."""
    task = get_task(task_name)
    
    # Create a mock user with context
    mock_user = MockUser(user_id=user_id, organization_id=organization_id)
    
    # Print details about the task being run
    print(f"\nRunning task: {task_name}")
    print(f"Context: organization_id={organization_id}, user_id={user_id}")
    print(f"Arguments: {json.dumps(kwargs, indent=2, default=str)}")
    
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
            
        print(f"\nTask submitted successfully!")
        print(f"Task ID: {result.id}")
        
        if wait:
            print("\nWaiting for task to complete...")
            start_time = time.time()
            result.get(timeout=timeout, propagate=False)
            
            elapsed = time.time() - start_time
            print(f"Task completed in {elapsed:.2f} seconds")
            
            if result.successful():
                print("\nResult:")
                print(json.dumps(result.result, indent=2, default=str))
            elif result.failed():
                print("\nTask failed with error:")
                print(result.traceback)
            else:
                print(f"\nUnexpected status: {result.status}")
            
    except Exception as e:
        print(f"\nError launching task: {e}")
        sys.exit(1)


if __name__ == "__main__":
    args, task_kwargs = parse_arguments()
    run_task(
        task_name=args.task_name,
        organization_id=args.organization_id,
        user_id=args.user_id,
        wait=args.wait,
        timeout=args.timeout,
        **task_kwargs
    )
