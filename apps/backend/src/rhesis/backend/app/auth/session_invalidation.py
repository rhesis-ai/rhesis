"""
Session Invalidation Module.

Tracks invalidated user sessions to properly implement logout.
JWT tokens are stateless, so we need to track when a user logged out
and reject tokens issued before that time.

For production deployments, consider using Redis for this.
For single-instance deployments, in-memory storage is sufficient.
"""

import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from rhesis.backend.logging import logger


class SessionInvalidationStore:
    """
    Tracks user logout timestamps to invalidate old session tokens.

    When a user logs out, we record the timestamp. Any JWT token
    with an 'iat' (issued at) before this timestamp is considered invalid.

    Thread-safe for concurrent access.
    """

    def __init__(self):
        # Maps user_id -> logout timestamp
        self._logout_times: Dict[str, datetime] = {}
        self._lock = threading.Lock()

    def invalidate_user_sessions(self, user_id: str) -> None:
        """
        Mark all current sessions for a user as invalid.

        Args:
            user_id: The user ID whose sessions should be invalidated
        """
        with self._lock:
            self._logout_times[user_id] = datetime.now(timezone.utc)
            logger.info(f"Invalidated all sessions for user {user_id}")

    def is_session_valid(self, user_id: str, issued_at: datetime) -> bool:
        """
        Check if a session token is still valid (not logged out).

        Args:
            user_id: The user ID from the token
            issued_at: The 'iat' timestamp from the JWT

        Returns:
            True if the session is valid, False if it was invalidated
        """
        with self._lock:
            logout_time = self._logout_times.get(user_id)

            if logout_time is None:
                # User never logged out, session is valid
                return True

            # Ensure issued_at is timezone-aware
            if issued_at.tzinfo is None:
                issued_at = issued_at.replace(tzinfo=timezone.utc)

            # Session is valid if it was issued AFTER the logout
            is_valid = issued_at > logout_time

            if not is_valid:
                logger.debug(
                    f"Session for user {user_id} rejected: "
                    f"issued at {issued_at}, logged out at {logout_time}"
                )

            return is_valid

    def clear_user_logout(self, user_id: str) -> None:
        """
        Clear logout tracking for a user (e.g., after successful login).

        This allows tokens issued at any time to be valid again.
        Useful if you want login to reset the invalidation.

        Args:
            user_id: The user ID to clear
        """
        with self._lock:
            self._logout_times.pop(user_id, None)

    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """
        Remove logout entries older than max_age_hours.

        This prevents unbounded memory growth. Tokens older than max_age
        would have expired anyway (assuming JWT expiry < max_age_hours).

        Args:
            max_age_hours: Remove entries older than this

        Returns:
            Number of entries removed
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed = 0

        with self._lock:
            expired_users = [
                user_id
                for user_id, logout_time in self._logout_times.items()
                if logout_time < cutoff
            ]
            for user_id in expired_users:
                del self._logout_times[user_id]
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} old logout entries")

        return removed

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the store."""
        with self._lock:
            return {
                "tracked_users": len(self._logout_times),
            }


# Global singleton instance
_store: Optional[SessionInvalidationStore] = None
_store_lock = threading.Lock()


def get_session_store() -> SessionInvalidationStore:
    """Get the global session invalidation store instance."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = SessionInvalidationStore()
    return _store


def invalidate_user_sessions(user_id: str) -> None:
    """Convenience function to invalidate user sessions."""
    get_session_store().invalidate_user_sessions(user_id)


def is_session_valid(user_id: str, issued_at: datetime) -> bool:
    """Convenience function to check session validity."""
    return get_session_store().is_session_valid(user_id, issued_at)


def clear_user_logout(user_id: str) -> None:
    """Convenience function to clear user logout tracking."""
    get_session_store().clear_user_logout(user_id)
