"""
Attribute Extraction Utility

Extracts attributes from OpenTelemetry protobuf messages.
"""

from typing import Any, Dict


class AttributeExtractor:
    """
    Utility class for extracting attributes from OTLP protobuf.

    Follows Single Responsibility Principle - only handles attribute extraction.
    """

    @staticmethod
    def extract(attributes) -> Dict[str, Any]:
        """
        Extract attributes from protobuf AttributeList to dictionary.

        Args:
            attributes: Protobuf attribute list

        Returns:
            Dict[str, Any]: Dictionary of attribute key-value pairs
        """
        result = {}

        for attr in attributes:
            key = attr.key
            value = attr.value

            # Handle different value types
            if value.HasField("string_value"):
                result[key] = value.string_value
            elif value.HasField("int_value"):
                result[key] = value.int_value
            elif value.HasField("double_value"):
                result[key] = value.double_value
            elif value.HasField("bool_value"):
                result[key] = value.bool_value
            elif value.HasField("array_value"):
                result[key] = AttributeExtractor._extract_array(value.array_value)
            elif value.HasField("kvlist_value"):
                result[key] = AttributeExtractor._extract_kvlist(value.kvlist_value)

        return result

    @staticmethod
    def _extract_array(array_value) -> list:
        """Extract array values from protobuf."""
        result = []
        for value in array_value.values:
            if value.HasField("string_value"):
                result.append(value.string_value)
            elif value.HasField("int_value"):
                result.append(value.int_value)
            elif value.HasField("double_value"):
                result.append(value.double_value)
            elif value.HasField("bool_value"):
                result.append(value.bool_value)
        return result

    @staticmethod
    def _extract_kvlist(kvlist_value) -> Dict[str, Any]:
        """Extract key-value list from protobuf."""
        return AttributeExtractor.extract(kvlist_value.values)
