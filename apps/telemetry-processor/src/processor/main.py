"""
Telemetry Processor Main Entry Point

Starts the gRPC server for receiving OpenTelemetry traces.
"""

import logging
import os
from concurrent import futures

import grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc

from processor.database import get_database_manager
from processor.grpc import APIKeyInterceptor, TelemetryTraceService
from processor.services import SpanRouter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def serve():
    """
    Start the telemetry processor gRPC server.

    Initializes all components and starts listening for trace data.
    """
    # Initialize database
    db_manager = get_database_manager()
    logger.info("Database initialized successfully")

    # Initialize span router with all processors
    span_router = SpanRouter()
    logger.info("Span router initialized with processors")

    # Create gRPC service
    trace_service = TelemetryTraceService(db_manager, span_router)

    # Create API key interceptor for authentication
    api_key_interceptor = APIKeyInterceptor()

    # Create gRPC server with interceptor
    max_workers = int(os.getenv("GRPC_MAX_WORKERS", "10"))
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        interceptors=(api_key_interceptor,),
    )

    # Register trace service
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
        trace_service,
        server,
    )

    # Start server
    port = os.getenv("PORT", "4317")
    server.add_insecure_port(f"[::]:{port}")

    logger.info(f"Starting telemetry processor on port {port} with {max_workers} workers")
    server.start()

    logger.info("Telemetry processor ready to receive traces")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down telemetry processor")
        server.stop(grace_period=5)
        db_manager.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    serve()
