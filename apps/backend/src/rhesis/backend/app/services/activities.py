"""
Service for tracking and aggregating recent activities across entities.

This service automatically discovers entities marked with ActivityTrackableMixin
and provides a unified view of recent CRUD operations.
"""

import inspect
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, contains_eager

from rhesis.backend.app import models
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.mixins import ActivityTrackableMixin
from rhesis.backend.app.schemas.services import ActivityItem, ActivityOperation
from rhesis.backend.logging import logger


class RecentActivitiesService:
    """Service for retrieving recent activities across all trackable entities."""

    @staticmethod
    def discover_trackable_models() -> Dict[str, Type[Base]]:
        """
        Automatically discover all models with ActivityTrackableMixin.

        Returns:
            Dict mapping model names to model classes
        """
        trackable_models = {}

        for name, obj in inspect.getmembers(models):
            # Check if it's a class that inherits from ActivityTrackableMixin
            if (
                inspect.isclass(obj)
                and issubclass(obj, ActivityTrackableMixin)
                and obj is not ActivityTrackableMixin
                and hasattr(obj, "__tablename__")
            ):
                trackable_models[name] = obj
                logger.debug(f"Discovered trackable model: {name}")

        logger.info(f"Discovered {len(trackable_models)} trackable models")
        return trackable_models

    @staticmethod
    def determine_operation(entity: Base) -> ActivityOperation:
        """
        Determine the operation type based on entity timestamps.

        Args:
            entity: The entity to check

        Returns:
            ActivityOperation enum value
        """
        # Check for soft delete
        if hasattr(entity, "deleted_at") and entity.deleted_at is not None:
            return ActivityOperation.DELETE

        # Check if entity was updated (with 1-second buffer for precision)
        if hasattr(entity, "created_at") and hasattr(entity, "updated_at"):
            if entity.created_at and entity.updated_at:
                # Add 1 second buffer to account for database timestamp precision
                time_diff = entity.updated_at - entity.created_at
                if time_diff > timedelta(seconds=1):
                    return ActivityOperation.UPDATE

        # Default to create
        return ActivityOperation.CREATE

    @staticmethod
    def entity_to_dict(entity: Base) -> Dict[str, Any]:
        """
        Convert SQLAlchemy entity to JSON-serializable dict.

        Args:
            entity: The entity to convert

        Returns:
            Dictionary with entity data
        """
        result = {}
        mapper = sa_inspect(entity.__class__)

        # Get all columns
        for column in mapper.columns:
            value = getattr(entity, column.name, None)

            # Handle special types
            if value is None:
                result[column.name] = None
            elif isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif hasattr(value, "__str__"):  # Handle UUIDs and other types
                result[column.name] = str(value)
            else:
                result[column.name] = value

        return result

    def get_recent_activities(
        self, db: Session, organization_id: Optional[str], limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get recent activities across all trackable entities.

        Args:
            db: Database session
            organization_id: Organization ID for filtering
            limit: Maximum number of activities to return

        Returns:
            Dictionary with activities list and total count
        """
        trackable_models = self.discover_trackable_models()

        if not trackable_models:
            logger.warning("No trackable models found")
            return {"activities": [], "total": 0}

        all_activities = []

        # Calculate how many records to fetch per model
        # Fetch more than needed to ensure we have enough after filtering
        per_model_limit = max(10, ceil(limit * 1.5 / len(trackable_models)))

        for model_name, model_class in trackable_models.items():
            try:
                # Build base query
                query = db.query(model_class)

                # Check if model has organization_id for filtering
                if organization_id and hasattr(model_class, "organization_id"):
                    query = query.filter(model_class.organization_id == organization_id)

                # Check if model has user relationship for eager loading
                has_user = hasattr(model_class, "user_id") and hasattr(model_class, "user")

                if has_user:
                    # Eager load user relationship to avoid N+1 queries
                    try:
                        query = query.outerjoin(model_class.user).options(
                            contains_eager(model_class.user)
                        )
                    except Exception as e:
                        logger.debug(f"Could not eager load user for {model_name}: {e}")

                # Order by updated_at descending to get most recent first
                if hasattr(model_class, "updated_at"):
                    query = query.order_by(model_class.updated_at.desc())

                # Fetch entities (including soft-deleted ones)
                entities = query.limit(per_model_limit).all()

                logger.debug(f"Found {len(entities)} {model_name} entities")

                # Process each entity
                for entity in entities:
                    try:
                        # Determine operation type
                        operation = self.determine_operation(entity)

                        # Get timestamp - use updated_at for most recent activity time
                        timestamp = getattr(entity, "updated_at", None) or getattr(
                            entity, "created_at", None
                        )

                        if not timestamp:
                            logger.warning(f"Skipping {model_name} entity without timestamp")
                            continue

                        # Get user if available
                        user_data = None
                        if has_user:
                            user_obj = getattr(entity, "user", None)
                            if user_obj:
                                user_data = {
                                    "id": str(user_obj.id),
                                    "email": user_obj.email,
                                    "name": user_obj.name,
                                    "given_name": user_obj.given_name,
                                    "family_name": user_obj.family_name,
                                    "picture": user_obj.picture,
                                    "is_active": user_obj.is_active,
                                    "organization_id": str(user_obj.organization_id)
                                    if user_obj.organization_id
                                    else None,
                                }

                        # Convert entity to dict
                        entity_data = self.entity_to_dict(entity)

                        # Create activity item
                        activity = ActivityItem(
                            entity_type=model_name,
                            entity_id=entity.id,
                            operation=operation,
                            timestamp=timestamp,
                            user=user_data,
                            entity_data=entity_data,
                        )

                        all_activities.append(activity)

                    except Exception as e:
                        logger.error(f"Error processing {model_name} entity: {e}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Error querying {model_name}: {e}", exc_info=True)
                continue

        # Sort all activities by timestamp descending
        all_activities.sort(key=lambda x: x.timestamp, reverse=True)

        # Return top N activities
        limited_activities = all_activities[:limit]

        logger.info(
            f"Returning {len(limited_activities)} activities from {len(all_activities)} total"
        )

        return {"activities": limited_activities, "total": len(limited_activities)}
