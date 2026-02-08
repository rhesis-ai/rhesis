"""
Template service for email notifications using Jinja2.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import jinja2

from rhesis.backend.logging.rhesis_logger import logger


class EmailTemplate(Enum):
    """Available email templates."""

    TASK_COMPLETION = "task_completion.html.jinja2"
    TEST_EXECUTION_SUMMARY = "test_execution_summary.html.jinja2"
    TEAM_INVITATION = "team_invitation.html.jinja2"
    TASK_ASSIGNMENT = "task_assignment.html.jinja2"
    WELCOME = "welcome.html.jinja2"
    EMAIL_VERIFICATION = "email_verification.html.jinja2"
    PASSWORD_RESET = "password_reset.html.jinja2"
    MAGIC_LINK = "magic_link.html.jinja2"


class TemplateService:
    """Service for loading and rendering HTML email templates using Jinja2."""

    def __init__(self):
        # Get template directory path
        self.template_dir = Path(__file__).parent / "templates"

        # Initialize Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.jinja_env.filters["datetime_format"] = self._datetime_format

        # Define required variables for each template
        self.template_variables = {
            EmailTemplate.TASK_COMPLETION: {
                "recipient_name",
                "task_name",
                "task_id",
                "status",
                "completed_at",
                "execution_time",
                "error_message",
                "frontend_url",
                # Note: test_run_id and test_set_id are optional (task-specific)
            },
            EmailTemplate.TEST_EXECUTION_SUMMARY: {
                "recipient_name",
                "task_name",
                "task_id",
                "status",
                "completed_at",
                "total_tests",
                "tests_passed",
                "tests_failed",
                "execution_time",
                "test_run_id",
                "status_details",
                "frontend_url",
                "test_set_name",
                "endpoint_name",
                "endpoint_url",
                "project_name",
            },
            EmailTemplate.TEAM_INVITATION: {
                "recipient_name",
                "recipient_email",
                "organization_name",
                "organization_website",
                "inviter_name",
                "inviter_email",
                "frontend_url",
            },
            EmailTemplate.TASK_ASSIGNMENT: {
                "assignee_name",
                "assigner_name",
                "task_title",
                "task_description",
                "task_id",
                "status_name",
                "priority_name",
                "entity_type",
                "entity_id",
                "entity_name",
                "created_at",
                "task_metadata",
                "frontend_url",
            },
            EmailTemplate.WELCOME: {
                "recipient_name",
                "recipient_email",
                "frontend_url",
                "calendar_link",
            },
            EmailTemplate.EMAIL_VERIFICATION: {
                "recipient_name",
                "verification_url",
            },
            EmailTemplate.PASSWORD_RESET: {
                "recipient_name",
                "reset_url",
            },
            EmailTemplate.MAGIC_LINK: {
                "recipient_name",
                "magic_link_url",
                "is_new_user",
            },
        }

    def _datetime_format(self, value, format="%Y-%m-%d %H:%M:%S"):
        """Custom Jinja2 filter for datetime formatting."""
        if isinstance(value, str):
            return value
        return value.strftime(format) if value else ""

    def render_template(self, template: EmailTemplate, variables: Dict[str, Any]) -> str:
        """
        Render an email template with the provided variables.

        Args:
            template: The email template to render
            variables: Dictionary of variables to pass to the template

        Returns:
            str: Rendered HTML content

        Note:
            Missing variables will be set to "N/A" automatically.
        """
        try:
            # Get the template
            jinja_template = self.jinja_env.get_template(template.value)

            # Prepare context with all required variables
            context = self._prepare_context(template, variables)

            # Render the template
            rendered_content = jinja_template.render(**context)

            logger.debug(
                f"Successfully rendered template {template.value} with {len(context)} variables"
            )
            return rendered_content

        except jinja2.TemplateNotFound:
            logger.error(f"Template not found: {template.value}")
            raise ValueError(f"Template not found: {template.value}")
        except jinja2.TemplateError as e:
            logger.error(f"Template rendering error for {template.value}: {str(e)}")
            raise ValueError(f"Template rendering error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error rendering template {template.value}: {str(e)}")
            raise

    def _prepare_context(
        self, template: EmailTemplate, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare the template context, filling missing variables with 'N/A'.

        Args:
            template: The email template being rendered
            variables: User-provided variables

        Returns:
            Dict[str, Any]: Complete context with all required variables
        """
        # Get required variables for this template
        required_vars = self.template_variables.get(template, set())

        # Start with provided variables
        context = variables.copy()

        # Add completed_at if not provided
        if "completed_at" not in context:
            context["completed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Fill missing required variables with 'N/A'
        missing_vars = []
        for var_name in required_vars:
            if var_name not in context or context[var_name] is None:
                context[var_name] = "N/A"
                missing_vars.append(var_name)

        # Log missing variables for debugging
        if missing_vars:
            logger.debug(
                f"Template {template.value} missing variables (set to N/A): {missing_vars}"
            )

        return context

    def get_template_variables(self, template: EmailTemplate) -> set:
        """
        Get the list of variables required by a template.

        Args:
            template: The email template

        Returns:
            set: Set of variable names required by the template
        """
        return self.template_variables.get(template, set()).copy()
