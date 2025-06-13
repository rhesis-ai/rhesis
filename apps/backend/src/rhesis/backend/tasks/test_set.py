import logging

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.worker import app
from rhesis.backend.tasks.base import BaseTask, with_tenant_context

# Set up logging
logger = logging.getLogger(__name__)


@app.task(base=BaseTask, name="rhesis.backend.tasks.count_test_sets", bind=True)
@with_tenant_context
def count_test_sets(self, db=None):
    """
    Task that counts the total number of test sets in the database.
    
    Using the with_tenant_context decorator, this task automatically:
    1. Creates a database session
    2. Sets the tenant context from the task headers
    3. Passes the session to the task function
    4. Closes the session when done
    
    All database operations will have the correct tenant context automatically.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    self.log_with_context('info', f"Starting count_test_sets task")

    try:
        # Update task state to show progress
        self.update_state(state="PROGRESS", meta={"status": "Counting test sets"})
        self.log_with_context('info', f"Starting database queries")

        # Get all test sets with the proper tenant context
        # The db session is already configured with the tenant context by the decorator
        test_sets = crud.get_test_sets(db)
        total_count = len(test_sets)
        self.log_with_context('info', f"Total test sets counted", total_count=total_count)

        # Get counts by visibility
        public_count = db.query(TestSet).filter(TestSet.visibility == "public").count()
        private_count = db.query(TestSet).filter(TestSet.visibility == "private").count()
        self.log_with_context('info', f"Visibility counts retrieved", 
                             public_count=public_count, 
                             private_count=private_count)

        # Get counts by published status
        published_count = db.query(TestSet).filter(TestSet.is_published).count()
        unpublished_count = db.query(TestSet).filter(~TestSet.is_published).count()
        self.log_with_context('info', f"Published status counts retrieved",
                             published_count=published_count,
                             unpublished_count=unpublished_count)

        result = {
            "total_count": total_count,
            "by_visibility": {"public": public_count, "private": private_count},
            "by_status": {"published": published_count, "unpublished": unpublished_count},
            "organization_id": org_id,
            "user_id": user_id
        }

        self.log_with_context('info', f"Task completed successfully", 
                             total_count=total_count,
                             public_count=public_count,
                             private_count=private_count)
        return result

    except Exception as e:
        self.log_with_context('error', f"Task failed", error=str(e))
        # The task will be automatically retried due to BaseTask settings
        raise
