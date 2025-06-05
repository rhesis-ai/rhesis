#!/usr/bin/env python
"""
Database Backend Chord Monitor

Specialized monitoring and recovery tool for Celery chord issues with database backends.
Provides detection, diagnosis, and recovery options for stuck chords.
"""

import sys
import os
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from celery.result import AsyncResult, GroupResult
from sqlalchemy.orm import Session

from rhesis.backend.app.database import SessionLocal, set_tenant
from rhesis.backend.app import crud
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.execution.db_chord_coordinator import coordinate_database_chord
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app


class DatabaseChordMonitor:
    """Monitor and recover database backend chords."""
    
    def __init__(self):
        self.app = app
        
    def get_stuck_chords(self, max_age_hours: float = 1.0) -> List[Dict[str, Any]]:
        """Find chords that have been stuck for more than max_age_hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        stuck_chords = []
        
        try:
            with SessionLocal() as db:
                # Find test runs that are still IN_PROGRESS but started more than max_age_hours ago
                in_progress_runs = crud.get_test_runs_by_status(db, RunStatus.IN_PROGRESS.value)
                
                for run in in_progress_runs:
                    # Check if run started before cutoff time
                    if run.created_at < cutoff_time:
                        # Check if this might be a stuck chord
                        attributes = run.attributes or {}
                        if 'group_id' in attributes or 'coordinator_task_id' in attributes:
                            stuck_chords.append({
                                'test_run_id': str(run.id),
                                'test_config_id': attributes.get('test_config_id'),
                                'group_id': attributes.get('group_id'),
                                'coordinator_task_id': attributes.get('coordinator_task_id'),
                                'created_at': run.created_at,
                                'age_hours': (datetime.utcnow() - run.created_at).total_seconds() / 3600,
                                'attributes': attributes
                            })
                            
        except Exception as e:
            logger.error(f"Error finding stuck chords: {e}")
            
        return stuck_chords
    
    def diagnose_chord(self, group_id: str, task_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Diagnose the status of a chord and its tasks."""
        diagnosis = {
            'group_id': group_id,
            'timestamp': datetime.utcnow().isoformat(),
            'database_backend': True,
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Check group result
            group_result = AsyncResult(group_id, app=self.app)
            diagnosis['group_status'] = group_result.status
            diagnosis['group_ready'] = group_result.ready()
            
            # If we have task IDs, check individual tasks
            if task_ids:
                task_statuses = []
                completed_count = 0
                failed_count = 0
                
                for task_id in task_ids:
                    try:
                        task_result = AsyncResult(task_id, app=self.app)
                        status = task_result.status
                        task_statuses.append({
                            'task_id': task_id,
                            'status': status,
                            'ready': task_result.ready(),
                            'successful': task_result.successful() if task_result.ready() else None
                        })
                        
                        if task_result.ready():
                            if task_result.successful():
                                completed_count += 1
                            else:
                                failed_count += 1
                                
                    except Exception as e:
                        task_statuses.append({
                            'task_id': task_id,
                            'status': 'ERROR',
                            'error': str(e)
                        })
                        failed_count += 1
                
                diagnosis['task_statuses'] = task_statuses
                diagnosis['completed_tasks'] = completed_count
                diagnosis['failed_tasks'] = failed_count
                diagnosis['pending_tasks'] = len(task_ids) - completed_count - failed_count
                
                # Analyze issues
                if completed_count + failed_count == len(task_ids):
                    if not group_result.ready():
                        diagnosis['issues'].append('All tasks complete but group not ready (database backend issue)')
                        diagnosis['recommendations'].append('Use manual chord recovery')
                
                if diagnosis['pending_tasks'] > 0:
                    diagnosis['issues'].append(f'{diagnosis["pending_tasks"]} tasks still pending')
                    diagnosis['recommendations'].append('Wait or investigate individual task issues')
                    
            else:
                diagnosis['issues'].append('No task IDs provided for detailed analysis')
                diagnosis['recommendations'].append('Provide task IDs for complete diagnosis')
                
        except Exception as e:
            diagnosis['error'] = str(e)
            diagnosis['issues'].append(f'Error during diagnosis: {str(e)}')
        
        return diagnosis
    
    def recover_stuck_chord(self, group_id: str, task_ids: List[str], callback_info: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to recover a stuck chord by executing the callback manually."""
        try:
            logger.info(f"Attempting manual recovery for chord group {group_id}")
            
            # Collect results from completed tasks
            results = []
            successful_count = 0
            
            for task_id in task_ids:
                try:
                    task_result = AsyncResult(task_id, app=self.app)
                    if task_result.ready() and task_result.successful():
                        results.append(task_result.result)
                        successful_count += 1
                    else:
                        results.append(None)  # Failed or pending task
                except Exception:
                    results.append(None)
            
            # Execute the callback with collected results
            callback_args = callback_info.get('args', [])
            callback_kwargs = callback_info.get('kwargs', {})
            
            # Call collect_results with the proper signature
            full_args = [results] + list(callback_args)
            
            logger.info(f"Executing manual chord recovery for group {group_id}")
            logger.info(f"Collected {successful_count} successful results out of {len(task_ids)} tasks")
            
            callback_result = collect_results.apply(
                args=full_args,
                kwargs=callback_kwargs
            )
            
            if callback_result.successful():
                logger.info(f"Manual chord recovery successful for group {group_id}")
                return {
                    'success': True,
                    'group_id': group_id,
                    'recovered_tasks': successful_count,
                    'total_tasks': len(task_ids),
                    'callback_result': callback_result.result
                }
            else:
                logger.error(f"Manual chord recovery callback failed for group {group_id}")
                return {
                    'success': False,
                    'group_id': group_id,
                    'error': 'callback_failed',
                    'callback_error': str(callback_result.result)
                }
                
        except Exception as e:
            logger.error(f"Error in manual chord recovery for group {group_id}: {e}")
            return {
                'success': False,
                'group_id': group_id,
                'error': str(e)
            }
    
    def restart_database_coordination(self, group_id: str, task_ids: List[str], callback_info: Dict[str, Any]) -> str:
        """Restart database chord coordination for a stuck chord."""
        try:
            logger.info(f"Restarting database coordination for group {group_id}")
            
            coordinator_task = coordinate_database_chord.delay(
                group_id=group_id,
                task_ids=task_ids,
                callback_info=callback_info
            )
            
            logger.info(f"Started new database chord coordinator: {coordinator_task.id}")
            return coordinator_task.id
            
        except Exception as e:
            logger.error(f"Error restarting database coordination: {e}")
            raise


def main():
    """Main CLI interface for database chord monitoring."""
    parser = argparse.ArgumentParser(description='Database Backend Chord Monitor')
    parser.add_argument('command', choices=['status', 'stuck', 'diagnose', 'recover', 'restart'],
                       help='Command to execute')
    parser.add_argument('--group-id', help='Group ID for diagnose/recover/restart commands')
    parser.add_argument('--task-ids', nargs='+', help='Task IDs for diagnose/recover/restart commands')
    parser.add_argument('--callback-info', help='JSON string with callback info for recover/restart')
    parser.add_argument('--max-hours', type=float, default=1.0, help='Max age in hours for stuck chord detection')
    
    args = parser.parse_args()
    
    monitor = DatabaseChordMonitor()
    
    if args.command == 'status':
        print("=== Database Backend Chord Monitor Status ===")
        print(f"Celery app: {monitor.app.main}")
        print(f"Result backend: {monitor.app.conf.result_backend}")
        print(f"Database backend detected: {bool('database' in monitor.app.conf.result_backend.lower() if monitor.app.conf.result_backend else False)}")
        
    elif args.command == 'stuck':
        print(f"=== Finding Stuck Chords (older than {args.max_hours} hours) ===")
        stuck_chords = monitor.get_stuck_chords(args.max_hours)
        
        if not stuck_chords:
            print("No stuck chords found.")
        else:
            for chord in stuck_chords:
                print(f"\nStuck Chord:")
                print(f"  Test Run ID: {chord['test_run_id']}")
                print(f"  Group ID: {chord.get('group_id', 'N/A')}")
                print(f"  Age: {chord['age_hours']:.2f} hours")
                print(f"  Created: {chord['created_at']}")
                
    elif args.command == 'diagnose':
        if not args.group_id:
            print("Error: --group-id required for diagnose command")
            sys.exit(1)
            
        print(f"=== Diagnosing Chord {args.group_id} ===")
        diagnosis = monitor.diagnose_chord(args.group_id, args.task_ids)
        
        print(f"Group Status: {diagnosis.get('group_status')}")
        print(f"Group Ready: {diagnosis.get('group_ready')}")
        
        if 'task_statuses' in diagnosis:
            print(f"Task Summary: {diagnosis.get('completed_tasks', 0)} completed, "
                  f"{diagnosis.get('failed_tasks', 0)} failed, "
                  f"{diagnosis.get('pending_tasks', 0)} pending")
        
        if diagnosis.get('issues'):
            print("\nIssues Found:")
            for issue in diagnosis['issues']:
                print(f"  - {issue}")
                
        if diagnosis.get('recommendations'):
            print("\nRecommendations:")
            for rec in diagnosis['recommendations']:
                print(f"  - {rec}")
                
    elif args.command in ['recover', 'restart']:
        if not args.group_id or not args.task_ids:
            print(f"Error: --group-id and --task-ids required for {args.command} command")
            sys.exit(1)
            
        if not args.callback_info:
            print(f"Error: --callback-info required for {args.command} command")
            sys.exit(1)
            
        try:
            import json
            callback_info = json.loads(args.callback_info)
        except Exception as e:
            print(f"Error parsing callback info JSON: {e}")
            sys.exit(1)
            
        if args.command == 'recover':
            print(f"=== Manually Recovering Chord {args.group_id} ===")
            result = monitor.recover_stuck_chord(args.group_id, args.task_ids, callback_info)
            
            if result['success']:
                print(f"Recovery successful!")
                print(f"Recovered {result['recovered_tasks']}/{result['total_tasks']} tasks")
            else:
                print(f"Recovery failed: {result.get('error')}")
                
        elif args.command == 'restart':
            print(f"=== Restarting Database Coordination for {args.group_id} ===")
            try:
                coordinator_id = monitor.restart_database_coordination(args.group_id, args.task_ids, callback_info)
                print(f"Started new coordinator: {coordinator_id}")
            except Exception as e:
                print(f"Restart failed: {e}")


if __name__ == '__main__':
    main() 