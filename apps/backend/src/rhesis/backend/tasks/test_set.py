import logging

from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.celery_app import app
from rhesis.backend.tasks import BaseTask

# Set up logging
logger = logging.getLogger(__name__)


@app.task(base=BaseTask, name="rhesis.tasks.count_test_sets", bind=True)
def count_test_sets(self):
    """Task that counts the total number of test sets in the database."""
    logger.info(f"Starting count_test_sets task with id: {self.request.id}")

    try:
        # Log attempt to get database session
        logger.info("Attempting to get database session")
        session = next(get_db())
        logger.info("Successfully obtained database session")

        try:
            # Update task state to show progress
            self.update_state(state="PROGRESS", meta={"status": "Counting test sets"})
            logger.info("Starting database queries")

            # Count all test sets
            total_count = session.query(TestSet).count()
            logger.info(f"Total test sets count: {total_count}")

            # Get counts by visibility
            public_count = session.query(TestSet).filter(TestSet.visibility == "public").count()
            private_count = session.query(TestSet).filter(TestSet.visibility == "private").count()
            logger.info(f"Visibility counts - public: {public_count}, private: {private_count}")

            # Get counts by published status
            published_count = session.query(TestSet).filter(TestSet.is_published).count()
            unpublished_count = session.query(TestSet).filter(~TestSet.is_published).count()
            logger.info(
                f"Published status counts - published: {published_count}, "
                f"unpublished: {unpublished_count}"
            )

            result = {
                "total_count": total_count,
                "by_visibility": {"public": public_count, "private": private_count},
                "by_status": {"published": published_count, "unpublished": unpublished_count},
            }

            logger.info(f"Task completed successfully with result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during database queries: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info("Closing database session")
            session.close()

    except Exception as e:
        logger.error(f"Task failed with error: {str(e)}", exc_info=True)
        # The task will be automatically retried due to BaseTask settings
        raise e
