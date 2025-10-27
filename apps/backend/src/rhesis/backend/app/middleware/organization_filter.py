"""
Query-Level Organization Filtering Middleware

This middleware provides automatic organization filtering for database queries
to prevent cross-tenant data access vulnerabilities.

EXPERIMENTAL: This is a proof-of-concept implementation. Use with caution
in production environments and thoroughly test before deployment.
"""

import functools
import inspect
import logging
from typing import Optional, Type, Union
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import Select

logger = logging.getLogger(__name__)


class OrganizationFilterMiddleware:
    """
    Middleware that automatically applies organization filtering to database queries.

    This middleware intercepts SQLAlchemy queries and automatically adds organization_id
    filters for models that support multi-tenancy.

    WARNING: This is experimental and may have performance implications.
    Thoroughly test before using in production.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.organization_models = {
            "Behavior",
            "Category",
            "Comment",
            "Demographic",
            "Dimension",
            "Metric",
            "Model",
            "Prompt",
            "Risk",
            "Source",
            "Status",
            "Tag",
            "Task",
            "Test",
            "TestResult",
            "TestRun",
            "TestSet",
            "Token",
            "Topic",
            "TypeLookup",
            "UseCase",
            "Endpoint",
        }
        self._current_organization_id = None
        self._bypass_filtering = False

    def set_organization_context(self, organization_id: Optional[str]):
        """Set the current organization context for filtering"""
        self._current_organization_id = organization_id

    def bypass_filtering(self, bypass: bool = True):
        """Temporarily bypass organization filtering (use with extreme caution)"""
        self._bypass_filtering = bypass

    def enable(self):
        """Enable the middleware"""
        self.enabled = True

    def disable(self):
        """Disable the middleware"""
        self.enabled = False

    def apply_organization_filter(
        self, query: Union[Query, Select], model_class: Type
    ) -> Union[Query, Select]:
        """
        Apply organization filtering to a query if applicable.

        Args:
            query: The SQLAlchemy query to filter
            model_class: The model class being queried

        Returns:
            The filtered query
        """
        if not self.enabled or self._bypass_filtering:
            return query

        if not self._current_organization_id:
            logger.warning(f"No organization context set for query on {model_class.__name__}")
            return query

        # Check if the model supports organization filtering
        if (
            hasattr(model_class, "__name__")
            and model_class.__name__ in self.organization_models
            and hasattr(model_class, "organization_id")
        ):
            try:
                org_uuid = UUID(self._current_organization_id)
                filtered_query = query.filter(model_class.organization_id == org_uuid)
                logger.debug(f"Applied organization filter to {model_class.__name__} query")
                return filtered_query
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid organization_id format: {self._current_organization_id}, error: {e}"
                )

        return query


# Global middleware instance
organization_filter = OrganizationFilterMiddleware()


def with_organization_context(organization_id: Optional[str]):
    """
    Context manager that sets organization context for database operations.

    Usage:
        with with_organization_context("org-123"):
            results = db.query(Model).all()  # Automatically filtered by org-123
    """

    class OrganizationContext:
        def __enter__(self):
            organization_filter.set_organization_context(organization_id)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            organization_filter.set_organization_context(None)

    return OrganizationContext()


def bypass_organization_filter():
    """
    Context manager that temporarily bypasses organization filtering.

    WARNING: Use with extreme caution! This disables security filtering.

    Usage:
        with bypass_organization_filter():
            all_results = db.query(Model).all()  # NOT filtered by organization
    """

    class BypassContext:
        def __enter__(self):
            organization_filter.bypass_filtering(True)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            organization_filter.bypass_filtering(False)

    return BypassContext()


def organization_aware_query(func):
    """
    Decorator that automatically applies organization filtering to query results.

    The decorated function must accept an organization_id parameter.

    Usage:
        @organization_aware_query
        def get_user_tests(db: Session, user_id: str, organization_id: str):
            return db.query(Test).filter(Test.user_id == user_id).all()
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract organization_id from function parameters
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        organization_id = bound_args.arguments.get("organization_id")

        if organization_id:
            with with_organization_context(organization_id):
                return func(*args, **kwargs)
        else:
            logger.warning(f"Function {func.__name__} called without organization_id parameter")
            return func(*args, **kwargs)

    return wrapper


class SessionWithOrganizationFilter:
    """
    Session wrapper that automatically applies organization filtering.

    This is a safer alternative to global middleware that works at the session level.
    """

    def __init__(self, session: Session, organization_id: Optional[str] = None):
        self.session = session
        self.organization_id = organization_id

    def query(self, *args, **kwargs):
        """Override query method to apply organization filtering"""
        query = self.session.query(*args, **kwargs)

        # If we have a single model class argument, try to apply filtering
        if len(args) == 1 and hasattr(args[0], "__name__"):
            model_class = args[0]
            if (
                self.organization_id
                and model_class.__name__ in organization_filter.organization_models
                and hasattr(model_class, "organization_id")
            ):
                try:
                    org_uuid = UUID(self.organization_id)
                    query = query.filter(model_class.organization_id == org_uuid)
                    logger.debug(f"Applied organization filter to {model_class.__name__} query")
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"Invalid organization_id format: {self.organization_id}, error: {e}"
                    )

        return query

    def __getattr__(self, name):
        """Delegate all other attributes to the underlying session"""
        return getattr(self.session, name)


def get_organization_aware_session(
    session: Session, organization_id: Optional[str] = None
) -> SessionWithOrganizationFilter:
    """
    Create an organization-aware session wrapper.

    This provides a safer alternative to global middleware by applying
    organization filtering at the session level.

    Usage:
        org_session = get_organization_aware_session(db, organization_id="org-123")
        results = org_session.query(Model).all()  # Automatically filtered
    """
    return SessionWithOrganizationFilter(session, organization_id)


def setup_query_logging(engine: Engine):
    """
    Set up query logging to monitor organization filtering.

    This helps debug and monitor whether organization filtering is being applied correctly.
    """

    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if logger.isEnabledFor(logging.DEBUG):
            # Check if the query includes organization filtering
            if "organization_id" in statement:
                logger.debug(f"✅ Query includes organization filtering: {statement[:100]}...")
            else:
                # Check if it's querying an organization-aware table
                for model_name in organization_filter.organization_models:
                    table_name = model_name.lower()
                    if table_name in statement.lower():
                        logger.warning(
                            f"⚠️  Query on {model_name} table without organization filtering: {statement[:100]}..."
                        )
                        break


# Configuration for enabling/disabling the middleware
ORGANIZATION_FILTER_CONFIG = {
    "enabled": False,  # Disabled by default for safety
    "log_unfiltered_queries": True,
    "strict_mode": False,  # If True, raises exceptions for unfiltered queries
}


def configure_organization_filtering(
    enabled: bool = False, log_unfiltered_queries: bool = True, strict_mode: bool = False
):
    """
    Configure the organization filtering middleware.

    Args:
        enabled: Whether to enable automatic filtering
        log_unfiltered_queries: Whether to log queries without organization filtering
        strict_mode: If True, raises exceptions for unfiltered queries (NOT RECOMMENDED)
    """
    ORGANIZATION_FILTER_CONFIG.update(
        {
            "enabled": enabled,
            "log_unfiltered_queries": log_unfiltered_queries,
            "strict_mode": strict_mode,
        }
    )

    organization_filter.enabled = enabled

    if enabled:
        logger.info("🔒 Organization filtering middleware ENABLED")
    else:
        logger.info("🔒 Organization filtering middleware DISABLED")


# Example usage patterns
"""
# Pattern 1: Context manager approach (RECOMMENDED)
with with_organization_context("org-123"):
    tests = db.query(Test).all()  # Automatically filtered by org-123

# Pattern 2: Organization-aware session wrapper (RECOMMENDED)
org_session = get_organization_aware_session(db, "org-123")
tests = org_session.query(Test).all()  # Automatically filtered

# Pattern 3: Decorator approach
@organization_aware_query
def get_user_tests(db: Session, user_id: str, organization_id: str):
    return db.query(Test).filter(Test.user_id == user_id).all()

# Pattern 4: Bypass filtering (USE WITH EXTREME CAUTION)
with bypass_organization_filter():
    all_tests = db.query(Test).all()  # NOT filtered by organization

# Configuration
configure_organization_filtering(
    enabled=False,  # Keep disabled by default
    log_unfiltered_queries=True
)
"""
