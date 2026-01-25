"""
Prompt preprocessing service for template placeholder substitution.

Supports placeholders like {TARGET_MODEL}, {PROJECT_NAME}, etc.
Used for Garak probes and other templated prompts that need
runtime context substitution.

Easily extensible by adding to the PLACEHOLDERS registry.
"""

from typing import Any, Callable, Dict, Optional

from rhesis.backend.logging.rhesis_logger import logger


class PromptPreprocessor:
    """
    Preprocessor for prompt templates with placeholder substitution.

    Used for Garak probes and other templated prompts that need
    runtime context substitution before sending to target endpoints.

    Usage:
        preprocessor = PromptPreprocessor()
        processed = preprocessor.process(prompt, endpoint=endpoint)

    Extending:
        Add new placeholders to PLACEHOLDERS dict with a resolver function.
        The resolver receives a context dict and returns the substitution value.
    """

    # Registry of placeholders and their resolver functions
    # Resolver receives a context dict and returns the substitution value
    PLACEHOLDERS: Dict[str, Callable[[Dict[str, Any]], str]] = {
        # Garak compatibility - addresses the target application by project name
        # Used in jailbreak prompts like "Hello, {TARGET_MODEL}. From now on..."
        "{TARGET_MODEL}": lambda ctx: (
            ctx.get("project_name") or ctx.get("endpoint_name") or "Assistant"
        ),
        # Explicit project name
        "{PROJECT_NAME}": lambda ctx: ctx.get("project_name") or "Unknown Project",
        # Explicit endpoint name
        "{ENDPOINT_NAME}": lambda ctx: ctx.get("endpoint_name") or "Unknown Endpoint",
        # Future extensibility examples (commented out):
        # "{ORGANIZATION_NAME}": lambda ctx: ctx.get("organization_name") or "Organization",
        # "{CURRENT_DATE}": lambda ctx: ctx.get("current_date") or datetime.now().isoformat(),
        # "{USER_ROLE}": lambda ctx: ctx.get("user_role") or "user",
    }

    def process(
        self,
        prompt: str,
        endpoint: Optional[Any] = None,
        **extra_context: Any,
    ) -> str:
        """
        Process prompt and substitute all known placeholders.

        Args:
            prompt: The prompt text with potential placeholders
            endpoint: Endpoint model for context extraction (optional)
            **extra_context: Additional context values to use for substitution

        Returns:
            Processed prompt with placeholders substituted
        """
        # Quick check - if no placeholders present, return as-is
        if not any(ph in prompt for ph in self.PLACEHOLDERS):
            return prompt

        # Build context from endpoint and extras
        context = self._build_context(endpoint, extra_context)

        # Apply substitutions
        result = prompt
        substitutions_made = []

        for placeholder, resolver in self.PLACEHOLDERS.items():
            if placeholder in result:
                try:
                    value = resolver(context)
                    result = result.replace(placeholder, str(value))
                    substitutions_made.append(f"{placeholder} -> {value}")
                except Exception as e:
                    # Keep placeholder if resolution fails
                    logger.warning(f"Failed to resolve placeholder {placeholder}: {e}")

        if substitutions_made:
            logger.debug(f"Prompt preprocessing applied: {', '.join(substitutions_made)}")

        return result

    def _build_context(
        self,
        endpoint: Optional[Any],
        extra_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build context dictionary from endpoint and related objects.

        Override this method in subclasses to add more context sources.

        Args:
            endpoint: Endpoint model instance (optional)
            extra_context: Additional context values

        Returns:
            Context dictionary for placeholder resolution
        """
        context: Dict[str, Any] = {}

        if endpoint:
            context["endpoint_name"] = getattr(endpoint, "name", None)
            context["endpoint_id"] = str(getattr(endpoint, "id", ""))

            # Access project via relationship (lazy-loaded by SQLAlchemy)
            project = getattr(endpoint, "project", None)
            if project:
                context["project_name"] = getattr(project, "name", None)
                context["project_id"] = str(getattr(project, "id", ""))

        # Merge in any extra context provided (overrides endpoint-derived values)
        context.update(extra_context)

        return context

    @classmethod
    def register_placeholder(
        cls,
        placeholder: str,
        resolver: Callable[[Dict[str, Any]], str],
    ) -> None:
        """
        Register a new placeholder at runtime.

        Args:
            placeholder: The placeholder string (e.g., "{CUSTOM}")
            resolver: Function that takes context dict and returns substitution value

        Example:
            PromptPreprocessor.register_placeholder(
                "{TIMESTAMP}",
                lambda ctx: datetime.now().isoformat()
            )
        """
        cls.PLACEHOLDERS[placeholder] = resolver
        logger.info(f"Registered new prompt placeholder: {placeholder}")

    @classmethod
    def list_placeholders(cls) -> list:
        """
        List all registered placeholders.

        Returns:
            List of placeholder strings
        """
        return list(cls.PLACEHOLDERS.keys())


# Singleton instance for convenience
prompt_preprocessor = PromptPreprocessor()
