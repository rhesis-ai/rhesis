"""
Task for collecting and processing test execution results.
"""

from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import BaseTask, email_notification
from rhesis.backend.tasks.execution.result_processor import TestRunProcessor
from rhesis.backend.worker import app


@email_notification(
    template=EmailTemplate.TEST_EXECUTION_SUMMARY,
    subject_template="Test Execution Complete: {test_set_name} - {status.title()}"
)
@app.task(base=BaseTask, bind=True, display_name="Test Execution Summary")
def collect_results(self, results, test_run_id: str) -> Dict[str, Any]:
    """
    Collect and process test execution results, then send summary email.
    
    This is a chord callback that receives results from parallel test execution tasks.
    The organization_id and user_id are passed via task headers and handled by BaseTask.before_start.
    
    Args:
        results: List of results from the parallel test execution tasks (automatically provided by chord)
        test_run_id: ID of the test run to collect results for
        
    Returns:
        Dict containing test execution summary
    """
    self.log_with_context('info', f"Starting result collection for test run {test_run_id}")
    self.log_with_context('debug', f"Received {len(results) if results else 0} results from parallel tasks")
    
    try:
        with self.get_db_session() as db:
            # Get test run
            test_run = crud.get_test_run(db, UUID(test_run_id))
            if not test_run:
                raise ValueError(f"Test run not found: {test_run_id}")
            
            # Set completion time now for consistent use throughout
            completion_time = datetime.utcnow()
            
            # Process test run results using the dedicated processor
            processor = TestRunProcessor(self.log_with_context)
            summary_data = processor.process_test_run_results(db, test_run, test_run_id, completion_time)
            
            self.log_with_context('info', f"Test run update completed for: {test_run_id}")
            
            return summary_data
            
    except Exception as e:
        self.log_with_context('error', f"Failed to collect results for test run {test_run_id}", error=str(e))
        raise 