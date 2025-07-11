"""
Template service for email notifications.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.notifications.email.templates.email_fragments import (
    TEXT_EXECUTION_TIME, TEXT_TEST_RUN_ID, TEXT_ERROR_DETAILS, TEXT_VIEW_RESULTS,
    HTML_EXECUTION_TIME_ROW, HTML_TEST_RUN_ID_ROW, HTML_ERROR_DETAILS_SECTION, HTML_VIEW_RESULTS_SECTION
)


class TemplateService:
    """Service for loading and rendering email templates."""
    
    def __init__(self):
        # Get template directory path
        self.template_dir = Path(__file__).parent / "templates"
    
    def load_template(self, template_name: str) -> str:
        """Load email template from file."""
        template_path = self.template_dir / template_name
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Email template not found: {template_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading email template {template_path}: {str(e)}")
            raise
    
    def render_task_completion_text(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        execution_time: Optional[str],
        error_message: Optional[str],
        test_run_id: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create plain text email content for task completion."""
        
        template = self.load_template("email_task_completion.txt")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Build conditional content
        execution_time_text = TEXT_EXECUTION_TIME.format(execution_time=execution_time) if execution_time else ""
        test_run_id_text = TEXT_TEST_RUN_ID.format(test_run_id=test_run_id) if test_run_id else ""
        error_details_text = TEXT_ERROR_DETAILS.format(error_message=error_message) if (status.lower() == 'failed' and error_message) else ""
        view_results_text = TEXT_VIEW_RESULTS.format(frontend_url=frontend_url, test_run_id=test_run_id) if (frontend_url and test_run_id) else ""
        
        return template.format(
            greeting=greeting,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            task_id=task_id,
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time_text,
            test_run_id=test_run_id_text,
            error_details=error_details_text,
            view_results_link=view_results_text
        )
    
    def render_task_completion_html(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        execution_time: Optional[str],
        error_message: Optional[str],
        test_run_id: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create HTML email content for task completion."""
        
        template = self.load_template("email_task_completion.html")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        status_color = "#28a745" if status.lower() == 'success' else "#dc3545"
        status_emoji = "✅" if status.lower() == 'success' else "❌"
        
        # Build conditional content
        execution_time_row = HTML_EXECUTION_TIME_ROW.format(execution_time=execution_time) if execution_time else ""
        test_run_id_row = HTML_TEST_RUN_ID_ROW.format(test_run_id=test_run_id) if test_run_id else ""
        error_details_section = HTML_ERROR_DETAILS_SECTION.format(error_message=error_message) if (status.lower() == 'failed' and error_message) else ""
        view_results_section = HTML_VIEW_RESULTS_SECTION.format(frontend_url=frontend_url, test_run_id=test_run_id) if (frontend_url and test_run_id) else ""
        
        return template.format(
            greeting=greeting,
            status_emoji=status_emoji,
            status_color=status_color,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            task_id=task_id,
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            execution_time_row=execution_time_row,
            test_run_id_row=test_run_id_row,
            error_details_section=error_details_section,
            view_results_section=view_results_section
        )
    
    def render_test_execution_summary_text(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        total_tests: int,
        tests_passed: int,
        tests_failed: int,
        execution_time: Optional[str],
        test_run_id: Optional[str],
        status_details: Optional[str],
        frontend_url: Optional[str],
        test_set_name: Optional[str],
        endpoint_name: Optional[str],
        endpoint_url: Optional[str],
        project_name: Optional[str]
    ) -> str:
        """Create plain text email content for test execution summary."""
        
        template = self.load_template("email_test_execution_summary.txt")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Build conditional content lines
        project_name_line = f"\n- Project: {project_name}" if project_name else ""
        test_set_name_line = f"\n- Test Set: {test_set_name}" if test_set_name else ""
        endpoint_info_line = ""
        if endpoint_name and endpoint_url:
            endpoint_info_line = f"\n- Endpoint: {endpoint_name} ({endpoint_url})"
        elif endpoint_name:
            endpoint_info_line = f"\n- Endpoint: {endpoint_name}"
        
        # Build test run link if available
        test_run_link = ""
        if frontend_url and test_run_id:
            test_run_link = f"\n\nView Results:\n{frontend_url}/test-runs/{test_run_id}"
        
        return template.format(
            greeting=greeting,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            project_name_line=project_name_line,
            test_set_name_line=test_set_name_line,
            endpoint_info_line=endpoint_info_line,
            total_tests=total_tests,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            execution_time=execution_time or "N/A",
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            test_run_link=test_run_link,
            status_details=status_details or ""
        )
    
    def render_test_execution_summary_html(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        total_tests: int,
        tests_passed: int,
        tests_failed: int,
        execution_time: Optional[str],
        test_run_id: Optional[str],
        status_details: Optional[str],
        frontend_url: Optional[str],
        test_set_name: Optional[str],
        endpoint_name: Optional[str],
        endpoint_url: Optional[str],
        project_name: Optional[str]
    ) -> str:
        """Create HTML email content for test execution summary."""
        
        template = self.load_template("email_test_execution_summary.html")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Determine colors and styling based on status
        if status.lower() == "success":
            status_color = "#28a745"
            status_emoji = "✅"
            status_bg_color = "#d4edda"
            status_border_color = "#c3e6cb"
            status_text_color = "#155724"
        elif status.lower() == "partial":
            status_color = "#ffc107"
            status_emoji = "⚠️"
            status_bg_color = "#fff3cd"
            status_border_color = "#ffeaa7"
            status_text_color = "#856404"
        else:  # failed
            status_color = "#dc3545"
            status_emoji = "❌"
            status_bg_color = "#f8d7da"
            status_border_color = "#f5c6cb"
            status_text_color = "#721c24"
        
        # Build conditional content rows
        project_name_row = ""
        if project_name:
            project_name_row = f"""
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Project:</td>
                <td style="padding: 8px 0;">{project_name}</td>
            </tr>"""
        
        test_set_name_row = ""
        if test_set_name:
            test_set_name_row = f"""
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Test Set:</td>
                <td style="padding: 8px 0;">{test_set_name}</td>
            </tr>"""
        
        endpoint_info_row = ""
        if endpoint_name:
            endpoint_display = f"{endpoint_name} ({endpoint_url})" if endpoint_url else endpoint_name
            endpoint_info_row = f"""
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Endpoint:</td>
                <td style="padding: 8px 0;">{endpoint_display}</td>
            </tr>"""
        
        # Build test run link section
        test_run_link_section = ""
        if frontend_url and test_run_id:
            test_run_link_section = f"""
    <div style="text-align: center; margin: 20px 0;">
        <a href="{frontend_url}/test-runs/{test_run_id}" 
           style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
            View Detailed Results
        </a>
    </div>"""
        
        return template.format(
            greeting=greeting,
            status_emoji=status_emoji,
            status_color=status_color,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            project_name_row=project_name_row,
            test_set_name_row=test_set_name_row,
            endpoint_info_row=endpoint_info_row,
            total_tests=total_tests,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            execution_time=execution_time or "N/A",
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            status_bg_color=status_bg_color,
            status_border_color=status_border_color,
            status_text_color=status_text_color,
            status_details=status_details or "",
            test_run_link_section=test_run_link_section
        ) 