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
    # Access context from task request
    org_id = getattr(self.request, 'organization_id', 'unknown')
    user_id = getattr(self.request, 'user_id', 'unknown')
    
    logger.info(f"Starting count_test_sets task with id: {self.request.id}")
    logger.info(f"Task context - organization_id: {org_id}, user_id: {user_id}")

    try:
        # Update task state to show progress
        self.update_state(state="PROGRESS", meta={"status": "Counting test sets"})
        logger.info("Starting database queries with tenant context: user_id={user_id}, org_id={org_id}")

        # Get all test sets with the proper tenant context
        # The db session is already configured with the tenant context by the decorator
        test_sets = crud.get_test_sets(db)
        total_count = len(test_sets)
        logger.info(f"Total test sets count: {total_count}")

        # Get counts by visibility
        public_count = db.query(TestSet).filter(TestSet.visibility == "public").count()
        private_count = db.query(TestSet).filter(TestSet.visibility == "private").count()
        logger.info(f"Visibility counts - public: {public_count}, private: {private_count}")

        # Get counts by published status
        published_count = db.query(TestSet).filter(TestSet.is_published).count()
        unpublished_count = db.query(TestSet).filter(~TestSet.is_published).count()
        logger.info(
            f"Published status counts - published: {published_count}, "
            f"unpublished: {unpublished_count}"
        )

        result = {
            "total_count": total_count,
            "by_visibility": {"public": public_count, "private": private_count},
            "by_status": {"published": published_count, "unpublished": unpublished_count},
            "organization_id": org_id,
            "user_id": user_id
        }

        logger.info(f"Task completed successfully with result: {result}")
        return result

    except Exception as e:
        logger.error(f"Task failed with error: {str(e)}", exc_info=True)
        # The task will be automatically retried due to BaseTask settings
        raise
