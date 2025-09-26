import inspect
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Type, TypeVar

from fastapi import Response
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.crud_utils import count_items
from rhesis.backend.logging import logger

T = TypeVar("T")


def with_count_header(model: Type):
    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger.info(f"🎨 [DECORATOR] @with_count_header starting for model {model.__name__}")
            response: Response = kwargs["response"]
            filter_expr = kwargs.get("filter")
            
            # Handle both old and new dependency patterns
            db_context = kwargs.get("db_context")
            if db_context:
                # New pattern: db_context contains (db, organization_id, user_id)
                # REUSE the same database session - no new connection needed!
                logger.info("🔄 [DECORATOR] Using NEW pattern - reusing existing database session")
                db, organization_id, user_id = db_context
                logger.info(f"📊 [DECORATOR] Executing count query for {model.__name__}")
                count = count_items(db, model, filter_expr, organization_id, user_id)
                response.headers["X-Total-Count"] = str(count)
                logger.info(f"✅ [DECORATOR] Count completed: {count} items")
            else:
                # Old pattern: separate db and tenant_context parameters
                logger.info("🔄 [DECORATOR] Using OLD pattern - separate db and tenant_context")
                db = kwargs.get("db")
                tenant_context = kwargs.get("tenant_context")
                organization_id = None
                user_id = None
                if tenant_context:
                    organization_id, user_id = tenant_context

                # For old pattern, db should already be a Session object (no context manager)
                if hasattr(db, 'query') or hasattr(db, 'execute'):
                    # Already a Session object - REUSE it!
                    logger.info("📊 [DECORATOR] Executing count query (old pattern)")
                    count = count_items(db, model, filter_expr, organization_id, user_id)
                    response.headers["X-Total-Count"] = str(count)
                    logger.info(f"✅ [DECORATOR] Count completed: {count} items")
                else:
                    # Fallback: if it's somehow a context manager, handle it
                    logger.warning("⚠️ [DECORATOR] Fallback: creating new connection for count")
                    with db as session:
                        count = count_items(session, model, filter_expr, organization_id, user_id)
                        response.headers["X-Total-Count"] = str(count)

            # Call original route function (await if async)
            logger.info("🎯 [DECORATOR] Calling original route function")
            result = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
            logger.info("🏁 [DECORATOR] @with_count_header completed")
            return result

        return wrapper

    return decorator
