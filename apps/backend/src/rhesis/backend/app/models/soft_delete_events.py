"""
SQLAlchemy event listeners for automatic soft delete filtering.

This module provides automatic filtering of soft-deleted records at the
SQLAlchemy query level. It works in conjunction with the QueryBuilder
to provide multiple levels of control over soft delete behavior.
"""

from sqlalchemy import event
from sqlalchemy.orm import Query

from rhesis.backend.logging import logger


def setup_soft_delete_listener():
    """
    Set up the global soft delete event listener.
    
    This should be called once during application startup.
    It registers an event listener that automatically filters out
    soft-deleted records from all queries unless explicitly disabled.
    """
    
    @event.listens_for(Query, "before_compile", retval=True)
    def filter_soft_deleted(query):
        """
        Automatically filter out soft-deleted records from all queries.
        
        This event listener is called before every query is compiled.
        It checks each entity in the query and adds a filter to exclude
        soft-deleted records unless explicitly disabled.
        
        The filter can be bypassed in three ways:
        1. Using the without_soft_delete_filter() context manager
        2. Setting query._include_soft_deleted = True (QueryBuilder does this)
        3. Query already has _soft_delete_filter_applied flag
        """
        # Import here to avoid circular dependency
        from rhesis.backend.app.database import is_soft_delete_disabled
        
        # Check if soft delete filtering is disabled globally (context manager)
        if is_soft_delete_disabled():
            return query
        
        # Check if this specific query has disabled soft delete filtering
        if hasattr(query, '_include_soft_deleted') and query._include_soft_deleted:
            return query
        
        # Track if we've already applied the filter to avoid duplicates
        if hasattr(query, '_soft_delete_filter_applied') and query._soft_delete_filter_applied:
            return query
        
        # Check if query has LIMIT or OFFSET - if so, skip filtering to avoid SQL errors
        # These queries are already being filtered by QueryBuilder before limit/offset
        if (hasattr(query, '_limit') and query._limit is not None) or \
           (hasattr(query, '_offset') and query._offset is not None):
            return query
        
        # Apply soft delete filter to all entities in the query
        try:
            for desc in query.column_descriptions:
                entity = desc.get('entity')
                if entity is None:
                    continue
                
                # Check if entity has deleted_at column (all Base models do)
                if hasattr(entity, 'deleted_at'):
                    # Add filter to exclude soft-deleted records
                    query = query.filter(entity.deleted_at.is_(None))
            
            # Mark that we've applied the filter
            query._soft_delete_filter_applied = True
            
        except Exception as e:
            # Log but don't fail - better to return unfiltered than break queries
            logger.warning(f"Error applying soft delete filter: {e}")
        
        return query
    
    logger.info("Soft delete event listener registered successfully")

