"""
Span Router

Routes spans to appropriate processors based on event category.
Follows the Strategy pattern for flexible span processing.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from processor.services.base import SpanProcessor
from processor.services.endpoint_usage import EndpointUsageProcessor
from processor.services.feature_usage import FeatureUsageProcessor
from processor.services.user_activity import UserActivityProcessor
from processor.utils import AttributeExtractor

logger = logging.getLogger(__name__)


class SpanRouter:
    """
    Routes spans to appropriate processors.

    Implements the Chain of Responsibility pattern where each processor
    checks if it can handle the span, and processes it if capable.
    """

    def __init__(self):
        """Initialize router with all available processors."""
        self.processors: List[SpanProcessor] = [
            UserActivityProcessor(),
            EndpointUsageProcessor(),
            FeatureUsageProcessor(),
        ]
        self.attribute_extractor = AttributeExtractor()
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_span(self, span, resource, session: Session) -> None:
        """
        Process a single span by routing to appropriate processor.

        Args:
            span: OTLP span protobuf
            resource: OTLP resource protobuf
            session: Database session

        Raises:
            ValueError: If no processor can handle the span
        """
        # Extract attributes
        span_attrs = self.attribute_extractor.extract(span.attributes)
        resource_attrs = self.attribute_extractor.extract(resource.attributes)

        # Merge attributes (span attributes take precedence)
        all_attributes = {**resource_attrs, **span_attrs}

        # Convert timestamp
        timestamp = datetime.fromtimestamp(span.start_time_unix_nano / 1e9)

        # Find appropriate processor
        processor = self._find_processor(all_attributes)

        if processor:
            try:
                processor.process(all_attributes, timestamp, session)
            except Exception as e:
                self.logger.error(f"Error in {processor.__class__.__name__}: {e}", exc_info=True)
                raise
        else:
            event_category = all_attributes.get("event.category", "unknown")
            self.logger.warning(f"No processor found for event category: {event_category}")

    def _find_processor(self, attributes: Dict[str, Any]) -> SpanProcessor:
        """
        Find a processor that can handle the given attributes.

        Args:
            attributes: Merged span attributes

        Returns:
            SpanProcessor or None if no processor can handle it
        """
        for processor in self.processors:
            if processor.can_process(attributes):
                return processor
        return None

    def add_processor(self, processor: SpanProcessor) -> None:
        """
        Add a custom processor to the router.

        Allows extending the system with new processors without
        modifying existing code (Open/Closed Principle).

        Args:
            processor: Custom span processor instance
        """
        self.processors.append(processor)
        self.logger.info(f"Added processor: {processor.__class__.__name__}")
