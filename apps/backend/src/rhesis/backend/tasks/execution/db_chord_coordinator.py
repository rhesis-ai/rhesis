"""
Database-specific chord coordination for reliable callback execution.

This module provides a workaround for Celery chord issues with database backends
by implementing manual coordination logic that handles database-specific limitations.
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.database import SessionLocal, set_tenant
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app


class DatabaseChordCoordinator:
    """
    Handles chord coordination for database backends.
    
    Provides reliable chord completion detection and callback execution
    that works around database backend limitations.
    """
    
    def __init__(self, group_id: str, task_ids: List[str], callback_info: Dict[str, Any]):
        self.group_id = group_id
        self.task_ids = task_ids
        self.callback_info = callback_info
        self.max_wait_time = 300  # 5 minutes max wait
        self.check_interval = 5   # Check every 5 seconds
        
    def wait_for_completion_and_execute_callback(self) -> Dict[str, Any]:
        """
        Wait for all tasks to complete and execute the callback.
        
        Returns:
            Dictionary with coordination results
        """
        start_time = datetime.utcnow()
        max_end_time = start_time + timedelta(seconds=self.max_wait_time)
        
        logger.info(f"Starting database chord coordination for group {self.group_id}")
        logger.info(f"Monitoring {len(self.task_ids)} tasks with {self.check_interval}s intervals")
        
        while datetime.utcnow() < max_end_time:
            try:
                # Check task completion status
                completion_status = self._check_task_completion()
                
                if completion_status['all_complete']:
                    logger.info(f"All tasks completed for group {self.group_id}")
                    
                    # Execute the callback with collected results
                    callback_result = self._execute_callback(completion_status['results'])
                    
                    return {
                        'success': True,
                        'group_id': self.group_id,
                        'completed_tasks': len(completion_status['successful_results']),
                        'failed_tasks': len(completion_status['failed_results']),
                        'callback_result': callback_result,
                        'coordination_time': (datetime.utcnow() - start_time).total_seconds()
                    }
                
                elif completion_status['any_failed']:
                    logger.warning(f"Some tasks failed for group {self.group_id}, executing callback anyway")
                    
                    # Execute callback even with failures
                    callback_result = self._execute_callback(completion_status['results'])
                    
                    return {
                        'success': True,
                        'group_id': self.group_id,
                        'completed_tasks': len(completion_status['successful_results']),
                        'failed_tasks': len(completion_status['failed_results']),
                        'callback_result': callback_result,
                        'coordination_time': (datetime.utcnow() - start_time).total_seconds(),
                        'had_failures': True
                    }
                
                else:
                    # Still waiting for tasks to complete
                    pending_count = len([s for s in completion_status['task_statuses'] if s != 'SUCCESS' and s != 'FAILURE'])
                    logger.debug(f"Group {self.group_id}: {pending_count} tasks still pending")
                    
                    # Wait before next check
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                logger.error(f"Error in chord coordination for group {self.group_id}: {e}")
                # Continue trying unless we're out of time
                time.sleep(self.check_interval)
        
        # Timeout reached
        logger.error(f"Chord coordination timeout for group {self.group_id}")
        return {
            'success': False,
            'group_id': self.group_id,
            'error': 'coordination_timeout',
            'coordination_time': self.max_wait_time
        }
    
    def _check_task_completion(self) -> Dict[str, Any]:
        """Check the completion status of all tasks in the group."""
        successful_results = []
        failed_results = []
        task_statuses = []
        
        for task_id in self.task_ids:
            try:
                result = AsyncResult(task_id, app=app)
                status = result.status
                task_statuses.append(status)
                
                if result.ready():
                    if result.successful():
                        successful_results.append(result.result)
                    else:
                        failed_results.append({
                            'task_id': task_id,
                            'error': str(result.result) if result.result else 'Unknown error',
                            'traceback': result.traceback
                        })
                        
            except Exception as e:
                logger.error(f"Error checking task {task_id}: {e}")
                task_statuses.append('ERROR')
                failed_results.append({
                    'task_id': task_id,
                    'error': f'Check failed: {str(e)}',
                    'traceback': None
                })
        
        # Determine completion status
        all_complete = all(status in ['SUCCESS', 'FAILURE'] for status in task_statuses)
        any_failed = any(status == 'FAILURE' for status in task_statuses) or len(failed_results) > 0
        
        # Combine results in the format expected by collect_results
        all_results = successful_results + [None for _ in failed_results]  # None for failed tasks
        
        return {
            'all_complete': all_complete,
            'any_failed': any_failed,
            'task_statuses': task_statuses,
            'successful_results': successful_results,
            'failed_results': failed_results,
            'results': all_results  # Combined results for callback
        }
    
    def _execute_callback(self, results: List[Any]) -> Dict[str, Any]:
        """Execute the chord callback with the collected results."""
        try:
            # Extract callback information
            callback_args = self.callback_info.get('args', [])
            callback_kwargs = self.callback_info.get('kwargs', {})
            
            # Call collect_results with the proper signature
            # The first argument should be the results from the chord
            full_args = [results] + list(callback_args)
            
            logger.info(f"Executing chord callback for group {self.group_id}")
            logger.debug(f"Callback args: {len(full_args)} args, {len(callback_kwargs)} kwargs")
            
            # Execute the callback
            callback_result = collect_results.apply(
                args=full_args,
                kwargs=callback_kwargs
            )
            
            if callback_result.successful():
                logger.info(f"Chord callback completed successfully for group {self.group_id}")
                return {
                    'status': 'SUCCESS',
                    'result': callback_result.result
                }
            else:
                logger.error(f"Chord callback failed for group {self.group_id}: {callback_result.result}")
                return {
                    'status': 'FAILURE',
                    'error': str(callback_result.result),
                    'traceback': callback_result.traceback
                }
                
        except Exception as e:
            logger.error(f"Error executing chord callback for group {self.group_id}: {e}")
            return {
                'status': 'ERROR',
                'error': str(e)
            }


@app.task(bind=True, max_retries=3, retry_backoff=True)
def coordinate_database_chord(self, group_id: str, task_ids: List[str], callback_info: Dict[str, Any]):
    """
    Task to coordinate chord completion for database backends.
    
    This task monitors a group of tasks and executes the callback when they complete,
    working around the limitations of Celery's built-in chord coordination with database backends.
    """
    try:
        coordinator = DatabaseChordCoordinator(group_id, task_ids, callback_info)
        result = coordinator.wait_for_completion_and_execute_callback()
        
        if result['success']:
            logger.info(f"Database chord coordination completed successfully for group {group_id}")
        else:
            logger.error(f"Database chord coordination failed for group {group_id}: {result.get('error')}")
            
            # Retry if coordination failed
            if self.request.retries < self.max_retries:
                logger.warning(f"Retrying database chord coordination (attempt {self.request.retries + 1}/{self.max_retries})")
                raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return result
        
    except Exception as e:
        logger.error(f"Error in database chord coordination for group {group_id}: {e}")
        
        # Retry on error
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying database chord coordination due to error (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
        else:
            # Final attempt failed, try to execute callback with empty results as fallback
            logger.error(f"Database chord coordination failed permanently for group {group_id}, executing fallback")
            try:
                coordinator = DatabaseChordCoordinator(group_id, task_ids, callback_info)
                fallback_result = coordinator._execute_callback([])  # Empty results
                return {
                    'success': False,
                    'group_id': group_id,
                    'error': str(e),
                    'fallback_executed': True,
                    'fallback_result': fallback_result
                }
            except Exception as fallback_error:
                logger.error(f"Fallback execution also failed: {fallback_error}")
                return {
                    'success': False,
                    'group_id': group_id,
                    'error': str(e),
                    'fallback_error': str(fallback_error)
                } 