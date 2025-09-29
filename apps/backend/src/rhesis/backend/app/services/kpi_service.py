from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session


class KPIService:
    """
    Service class for handling KPI business logic.

    Follows your existing architecture patterns by using direct SQL queries
    within the service layer, similar to other services in your codebase.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_platform_metrics(self) -> Dict[str, Any]:
        """
        Get platform-wide KPIs for internal observability dashboard.

        Returns:
            Dict containing platform-wide metrics including users, tests,
            test runs, and test results with pass/fail rates.

        Raises:
            Exception: If any database query fails or data processing error occurs
        """
        # Get all metrics using direct SQL queries
        users_metrics = self._get_users_metrics()
        tests_metrics = self._get_tests_metrics()
        test_runs_metrics = self._get_test_runs_metrics()
        test_results_metrics = self._get_test_results_metrics()

        # Calculate derived metrics
        pass_rate = self._calculate_pass_rate(
            test_results_metrics["passed"], test_results_metrics["total"]
        )

        return {
            "scope": "platform_wide",
            "users": users_metrics,
            "tests": tests_metrics,
            "test_runs": test_runs_metrics,
            "test_results": {
                **test_results_metrics,
                "pass_rate": pass_rate,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _get_users_metrics(self) -> Dict[str, int]:
        """Get user-related metrics."""
        # Total active users
        users_query = text('SELECT COUNT(*) as total_users FROM "user" WHERE is_active = true')
        users_result = self.db.execute(users_query).fetchone()

        # Active users who signed in (last 30 days)
        signins_query = text("""
            SELECT COUNT(*) as active_users_30d FROM "user" 
            WHERE last_login_at >= NOW() - INTERVAL '30 days'
        """)
        signins_result = self.db.execute(signins_query).fetchone()

        return {
            "total": users_result[0] if users_result else 0,
            "active_users_30d": signins_result[0] if signins_result else 0,
        }

    def _get_tests_metrics(self) -> Dict[str, int]:
        """Get test-related metrics."""
        tests_query = text("SELECT COUNT(*) as total_tests FROM test")
        tests_result = self.db.execute(tests_query).fetchone()

        return {"total": tests_result[0] if tests_result else 0}

    def _get_test_runs_metrics(self) -> Dict[str, Any]:
        """Get test run-related metrics."""
        # Total test runs
        testruns_query = text("SELECT COUNT(*) as total_test_runs FROM test_run")
        testruns_result = self.db.execute(testruns_query).fetchone()

        # Test runs by status
        status_query = text("""
            SELECT s.name as status, COUNT(*) as count 
            FROM test_run tr 
            JOIN status s ON tr.status_id = s.id 
            GROUP BY s.name
            ORDER BY count DESC
        """)
        status_results = self.db.execute(status_query).fetchall()

        # Test runs timeline (last 6 months)
        timeline_query = text("""
            SELECT 
                DATE_TRUNC('month', tr.created_at) as month,
                COUNT(*) as count
            FROM test_run tr 
            WHERE tr.created_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', tr.created_at)
            ORDER BY month
        """)
        timeline_results = self.db.execute(timeline_query).fetchall()

        return {
            "total": testruns_result[0] if testruns_result else 0,
            "by_status": [{"status": row[0], "count": row[1]} for row in status_results],
            "timeline": [
                {"month": row[0].isoformat(), "count": row[1]} for row in timeline_results
            ],
        }

    def _get_test_results_metrics(self) -> Dict[str, int]:
        """Get test result-related metrics."""
        test_results_query = text("""
            SELECT 
                COUNT(*) as total_results,
                COUNT(CASE WHEN (
                    SELECT COUNT(*) FROM jsonb_each(test_metrics->'metrics') 
                    WHERE value->>'is_successful' = 'true'
                ) > (
                    SELECT COUNT(*) FROM jsonb_each(test_metrics->'metrics') 
                    WHERE value->>'is_successful' = 'false'
                ) THEN 1 END) as passed_results,
                COUNT(CASE WHEN (
                    SELECT COUNT(*) FROM jsonb_each(test_metrics->'metrics') 
                    WHERE value->>'is_successful' = 'false'
                ) >= (
                    SELECT COUNT(*) FROM jsonb_each(test_metrics->'metrics') 
                    WHERE value->>'is_successful' = 'true'
                ) THEN 1 END) as failed_results
            FROM test_result tr
            WHERE test_metrics IS NOT NULL
        """)
        test_results_result = self.db.execute(test_results_query).fetchone()

        return {
            "total": test_results_result[0] if test_results_result else 0,
            "passed": test_results_result[1] if test_results_result else 0,
            "failed": test_results_result[2] if test_results_result else 0,
        }

    def _calculate_pass_rate(self, passed: int, total: int) -> float:
        """Calculate pass rate percentage."""
        return round((passed / total * 100) if total > 0 else 0, 2)
