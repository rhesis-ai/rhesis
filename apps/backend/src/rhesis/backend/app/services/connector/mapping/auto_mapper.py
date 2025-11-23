"""Auto-mapper service for SDK function parameter detection."""

from typing import Any, Dict, List

from rhesis.backend.logging import logger

from .patterns import MappingPatterns


class AutoMapper:
    """Heuristic-based mapping detection for all standard fields."""

    def generate_mappings(
        self,
        function_name: str,
        parameters: Dict[str, Dict[str, Any]],
        return_type: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Auto-detect mappings from function signature.

        Args:
            function_name: Name of the function
            parameters: Function parameters with type and requirement info
            return_type: Function return type
            description: Function description

        Returns:
            {
                "request_mapping": {"message": "{{ input }}", ...},
                "response_mapping": {"output": "{{ response }}", ...},
                "confidence": 0.8,
                "matched_fields": ["input", "session_id"],
                "missing_fields": ["context", "metadata", "tool_calls"]
            }
        """
        param_names = list(parameters.keys())
        request_template = {}
        matched_fields = []

        # Iterate through all configured standard fields
        for field_config in MappingPatterns.STANDARD_FIELDS:
            match = self._find_best_match(param_names, field_config.pattern_type)
            if match:
                param_name, match_confidence = match
                request_template[param_name] = field_config.template_var
                matched_fields.append(field_config.name)
                logger.debug(
                    f"Matched {field_config.name} → {param_name} "
                    f"(confidence: {match_confidence:.2f})"
                )

        # Auto-detect output mappings (basic heuristics)
        response_mapping = self._infer_output_mappings(return_type)

        # Calculate confidence
        confidence = self._calculate_confidence(matched_fields)

        # Determine missing fields
        all_field_names = [f.name for f in MappingPatterns.STANDARD_FIELDS]
        missing_fields = [f for f in all_field_names if f not in matched_fields]

        logger.info(
            f"Auto-mapping for {function_name}: "
            f"{len(matched_fields)} matched ({matched_fields}), "
            f"{len(missing_fields)} missing ({missing_fields}), "
            f"confidence: {confidence:.2f}"
        )

        return {
            "request_mapping": request_template,
            "response_mapping": response_mapping,
            "confidence": confidence,
            "matched_fields": matched_fields,
            "missing_fields": missing_fields,
        }

    def _find_best_match(self, param_names: List[str], field_type: str) -> tuple[str, float] | None:
        """
        Find the best matching parameter for a field type.

        Args:
            param_names: List of parameter names to search
            field_type: Field type to match against

        Returns:
            Tuple of (param_name, confidence) or None if no match found
        """
        best_match = None
        best_confidence = 0.0

        for param_name in param_names:
            matches, confidence = MappingPatterns.match_parameter(param_name, field_type)
            if matches and confidence > best_confidence:
                best_match = param_name
                best_confidence = confidence

        return (best_match, best_confidence) if best_match else None

    def _infer_output_mappings(self, return_type: str) -> Dict[str, str]:
        """
        Infer basic output mappings based on return type.

        Uses fallback patterns with Jinja2 'or' syntax for flexibility.
        Creates mappings for all standard fields plus "output".

        Args:
            return_type: Function return type

        Returns:
            Dict of standard field → Jinja2 template mappings
        """
        # Fallback patterns for common field names
        fallback_patterns = {
            "output": ["response", "result", "output", "content", "text"],
            "session_id": ["session_id", "conversation_id", "conv_id", "thread_id", "chat_id"],
            "context": ["context", "sources", "documents", "chunks"],
            "metadata": ["metadata", "meta", "info"],
            "tool_calls": ["tool_calls", "tools", "functions", "function_calls"],
        }

        # Build response mapping with fallback patterns
        response_mapping = {}

        # Add output field (special case - always included)
        output_pattern = " or ".join(fallback_patterns["output"])
        response_mapping["output"] = f"{{{{ {output_pattern} }}}}"

        # Add all standard fields with fallback patterns
        for field_config in MappingPatterns.STANDARD_FIELDS:
            if field_config.name in fallback_patterns:
                pattern = " or ".join(fallback_patterns[field_config.name])
                response_mapping[field_config.name] = f"{{{{ {pattern} }}}}"

        return response_mapping

    def _calculate_confidence(self, matched_fields: List[str]) -> float:
        """
        Calculate mapping confidence based on matched fields.

        Uses weights defined in STANDARD_FIELDS configuration.
        Confidence >= 0.7 is considered high and triggers auto-mapping.
        Confidence < 0.7 triggers LLM fallback.

        Args:
            matched_fields: List of successfully matched field names

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.0

        for field_config in MappingPatterns.STANDARD_FIELDS:
            if field_config.name in matched_fields:
                confidence += field_config.confidence_weight

        return confidence
