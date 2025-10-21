"""
Telemetry Processor Service

This service receives OTLP data from the OpenTelemetry Collector
and writes it to PostgreSQL analytics tables.
"""

import logging
import os
from concurrent import futures
from datetime import datetime
from uuid import uuid4

import grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

Base = declarative_base()


# Database models for analytics
class UserActivity(Base):
    """User activity events (login, logout, session)"""

    __tablename__ = "analytics_user_activity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(32), nullable=False, index=True)  # Hashed, not UUID
    organization_id = Column(String(32), index=True)  # Hashed, not UUID
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    session_id = Column(String(255))
    deployment_type = Column(String(50))
    event_metadata = Column(JSON)


class EndpointUsage(Base):
    """API endpoint usage tracking"""

    __tablename__ = "analytics_endpoint_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10))
    user_id = Column(String(32), index=True)  # Hashed, not UUID
    organization_id = Column(String(32), index=True)  # Hashed, not UUID
    status_code = Column(Integer)
    duration_ms = Column(Float)
    timestamp = Column(DateTime, nullable=False, index=True)
    deployment_type = Column(String(50))
    event_metadata = Column(JSON)


class FeatureUsage(Base):
    """Feature-specific usage tracking"""

    __tablename__ = "analytics_feature_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    feature_name = Column(String(100), nullable=False, index=True)
    user_id = Column(String(32), index=True)  # Hashed, not UUID
    organization_id = Column(String(32), index=True)  # Hashed, not UUID
    action = Column(String(100))
    timestamp = Column(DateTime, nullable=False, index=True)
    deployment_type = Column(String(50))
    event_metadata = Column(JSON)


class TelemetryTraceService(trace_service_pb2_grpc.TraceServiceServicer):
    """gRPC service that receives traces and writes to PostgreSQL"""

    def __init__(self, db_session_maker):
        self.db_session_maker = db_session_maker

    def Export(self, request: ExportTraceServiceRequest, context):
        """Handle incoming trace data"""
        try:
            session = self.db_session_maker()

            for resource_span in request.resource_spans:
                for scope_span in resource_span.scope_spans:
                    for span in scope_span.spans:
                        self._process_span(span, resource_span.resource, session)

            session.commit()
            session.close()

            logger.info(
                f"Successfully processed {len(request.resource_spans)} resource spans"
            )

            return ExportTraceServiceResponse()

        except Exception as e:
            logger.error(f"Error processing trace: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error processing trace: {str(e)}")
            return ExportTraceServiceResponse()

    def _process_span(self, span, resource, session):
        """Process individual span and extract analytics data"""
        attributes = self._extract_attributes(span.attributes)
        resource_attrs = self._extract_attributes(resource.attributes)

        # Merge attributes
        all_attrs = {**resource_attrs, **attributes}

        # Determine event category
        event_category = all_attrs.get("event.category", "unknown")
        timestamp = datetime.fromtimestamp(span.start_time_unix_nano / 1e9)

        # Extract common fields
        user_id = all_attrs.get("user.id")
        org_id = all_attrs.get("organization.id")
        deployment_type = all_attrs.get("deployment.type", "unknown")

        # Route to appropriate table based on category
        if event_category == "user_activity":
            self._insert_user_activity(
                all_attrs, timestamp, user_id, org_id, deployment_type, session
            )

        elif event_category == "endpoint_usage":
            self._insert_endpoint_usage(
                all_attrs, timestamp, user_id, org_id, deployment_type, session
            )

        elif event_category == "feature_usage":
            self._insert_feature_usage(
                all_attrs, timestamp, user_id, org_id, deployment_type, session
            )

    def _extract_attributes(self, attributes):
        """Extract attributes from protobuf to dict"""
        result = {}
        for attr in attributes:
            key = attr.key
            value = attr.value

            if value.HasField("string_value"):
                result[key] = value.string_value
            elif value.HasField("int_value"):
                result[key] = value.int_value
            elif value.HasField("double_value"):
                result[key] = value.double_value
            elif value.HasField("bool_value"):
                result[key] = value.bool_value

        return result

    def _insert_user_activity(
        self, attrs, timestamp, user_id, org_id, deployment_type, session
    ):
        """Insert user activity record"""
        try:
            logger.info(
                f"Inserting user activity: event_type={attrs.get('event.type')}, user_id={user_id}, org_id={org_id}"
            )
            activity = UserActivity(
                user_id=user_id,
                organization_id=org_id,
                event_type=attrs.get("event.type", "unknown"),
                timestamp=timestamp,
                session_id=attrs.get("session.id"),
                deployment_type=deployment_type,
                event_metadata={
                    k: v
                    for k, v in attrs.items()
                    if k
                    not in [
                        "user.id",
                        "organization.id",
                        "event.type",
                        "session.id",
                        "deployment.type",
                    ]
                },
            )
            session.add(activity)
            logger.info("Successfully added user activity to session")
        except Exception as e:
            logger.error(f"Error inserting user activity: {e}")

    def _insert_endpoint_usage(
        self, attrs, timestamp, user_id, org_id, deployment_type, session
    ):
        """Insert endpoint usage record"""
        try:
            endpoint_usage = EndpointUsage(
                endpoint=attrs.get("http.route", attrs.get("http.url", "unknown")),
                method=attrs.get("http.method"),
                user_id=user_id,
                organization_id=org_id,
                status_code=attrs.get("http.status_code"),
                duration_ms=attrs.get("duration_ms"),
                timestamp=timestamp,
                deployment_type=deployment_type,
                event_metadata={
                    k: v
                    for k, v in attrs.items()
                    if k
                    not in [
                        "http.route",
                        "http.url",
                        "http.method",
                        "user.id",
                        "organization.id",
                        "http.status_code",
                        "duration_ms",
                        "deployment.type",
                    ]
                },
            )
            session.add(endpoint_usage)
        except Exception as e:
            logger.error(f"Error inserting endpoint usage: {e}")

    def _insert_feature_usage(
        self, attrs, timestamp, user_id, org_id, deployment_type, session
    ):
        """Insert feature usage record"""
        try:
            feature_usage = FeatureUsage(
                feature_name=attrs.get("feature.name", "unknown"),
                user_id=user_id,
                organization_id=org_id,
                action=attrs.get("feature.action"),
                timestamp=timestamp,
                deployment_type=deployment_type,
                event_metadata={
                    k: v
                    for k, v in attrs.items()
                    if k
                    not in [
                        "feature.name",
                        "user.id",
                        "organization.id",
                        "feature.action",
                        "deployment.type",
                    ]
                },
            )
            session.add(feature_usage)
        except Exception as e:
            logger.error(f"Error inserting feature usage: {e}")


def create_database_engine():
    """Create database engine from environment variables"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Construct from parts
        user = os.getenv("SQLALCHEMY_DB_USER", "rhesis-user")
        password = os.getenv("SQLALCHEMY_DB_PASS", "your-secured-password")
        host = os.getenv("SQLALCHEMY_DB_HOST", "postgres")
        port = os.getenv("SQLALCHEMY_DB_PORT", "5432")
        db_name = os.getenv("SQLALCHEMY_DB_NAME", "rhesis-db")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    engine = create_engine(db_url, pool_pre_ping=True)

    # Create tables if they don't exist
    Base.metadata.create_all(engine)

    return engine


def serve():
    """Start the gRPC server"""
    engine = create_database_engine()
    session_maker = sessionmaker(bind=engine)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
        TelemetryTraceService(session_maker), server
    )

    port = os.getenv("PORT", "4317")
    server.add_insecure_port(f"[::]:{port}")

    logger.info(f"Starting telemetry processor on port {port}")
    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down telemetry processor")
        server.stop(0)


if __name__ == "__main__":
    serve()
