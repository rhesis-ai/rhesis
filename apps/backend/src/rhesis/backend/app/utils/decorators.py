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
            
            # Handle multiple dependency patterns for maximum compatibility
            db_context = kwargs.get("db_context")
            db = kwargs.get("db")
            tenant_context = kwargs.get("tenant_context")
            
            if db_context:
                # Pattern 1: Combined db_context (db, organization_id, user_id)
                logger.info("🔄 [DECORATOR] Using COMBINED pattern - db_context tuple")
                db, organization_id, user_id = db_context
                logger.info(f"📊 [DECORATOR] Executing count query for {model.__name__}")
                count = count_items(db, model, filter_expr, organization_id, user_id)
                response.headers["X-Total-Count"] = str(count)
                logger.info(f"✅ [DECORATOR] Count completed: {count} items")
                
            elif db and tenant_context:
                # Pattern 2: Separate db (with session variables) + tenant_context
                logger.info("🔄 [DECORATOR] Using SEPARATE pattern - db + tenant_context")
                organization_id, user_id = tenant_context
                logger.info(f"📊 [DECORATOR] Executing count query for {model.__name__}")
                count = count_items(db, model, filter_expr, organization_id, user_id)
                response.headers["X-Total-Count"] = str(count)
                logger.info(f"✅ [DECORATOR] Count completed: {count} items")
                
            elif db:
                # Pattern 3: Just db session (legacy or tenant_db_session with RLS only)
                logger.info("🔄 [DECORATOR] Using DB-ONLY pattern - checking for session variables")
                
                # Check if we have tenant_context available for fallback
                if tenant_context:
                    organization_id, user_id = tenant_context
                    logger.info(f"📊 [DECORATOR] Using explicit parameters as fallback for {model.__name__}")
                    count = count_items(db, model, filter_expr, organization_id, user_id)
                else:
                    # Try RLS-only approach, but handle gracefully if session variables aren't set
                    try:
                        logger.info(f"📊 [DECORATOR] Attempting RLS-only count for {model.__name__}")
                        count = count_items(db, model, filter_expr, None, None)
                    except Exception as e:
                        if "unrecognized configuration parameter" in str(e):
                            logger.warning("⚠️ [DECORATOR] Session variables not set, returning 0 count")
                            count = 0
                        else:
                            raise
                
                response.headers["X-Total-Count"] = str(count)
                logger.info(f"✅ [DECORATOR] Count completed: {count} items")
                
            else:
                logger.error("❌ [DECORATOR] No valid database session found in parameters")
                response.headers["X-Total-Count"] = "0"

            # Call original route function (await if async)
            logger.info("🎯 [DECORATOR] Calling original route function")
            result = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
            logger.info("🏁 [DECORATOR] @with_count_header completed")
            return result

        return wrapper

    return decorator
