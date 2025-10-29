"""
Telemetry Trace Service

gRPC service implementation for receiving and processing OpenTelemetry traces.
"""

import logging

import grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from processor.database import DatabaseManager
from processor.services import SpanRouter

logger = logging.getLogger(__name__)


class TelemetryTraceService(trace_service_pb2_grpc.TraceServiceServicer):
    """
    gRPC service that receives OTLP traces and writes to PostgreSQL.

    Implements the OpenTelemetry Trace Service protocol.
    Uses dependency injection for database and span routing.
    """

    def __init__(self, db_manager: DatabaseManager, span_router: SpanRouter):
        """
        Initialize the trace service.

        Args:
            db_manager: Database manager for session creation
            span_router: Router for processing spans
        """
        self.db_manager = db_manager
        self.span_router = span_router
        self.logger = logging.getLogger(self.__class__.__name__)

    def Export(
        self,
        request: ExportTraceServiceRequest,
        context: grpc.ServicerContext,
    ) -> ExportTraceServiceResponse:
        """
        Handle incoming trace export requests.

        Args:
            request: OTLP trace export request
            context: gRPC service context

        Returns:
            ExportTraceServiceResponse: Success/failure response
        """
        try:
            session = self.db_manager.get_session()

            try:
                span_count = 0

                # Process all spans in the request
                for resource_span in request.resource_spans:
                    resource = resource_span.resource

                    for scope_span in resource_span.scope_spans:
                        for span in scope_span.spans:
                            self.span_router.process_span(span, resource, session)
                            span_count += 1

                # Commit all changes
                session.commit()

                self.logger.info(
                    f"Successfully processed {span_count} spans "
                    f"from {len(request.resource_spans)} resources"
                )

                return ExportTraceServiceResponse()

            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error processing trace export: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error processing trace: {str(e)}")
            return ExportTraceServiceResponse()
