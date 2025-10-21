FROM otel/opentelemetry-collector-contrib:0.97.0

# Copy configuration file
COPY otel-collector-config.yaml /etc/otelcol-contrib/config.yaml

# Expose ports
# 4317 - OTLP gRPC receiver
# 4318 - OTLP HTTP receiver
# 8888 - Prometheus metrics exposed by the collector
# 8889 - Prometheus exporter metrics
# 13133 - health_check extension
EXPOSE 4317 4318 8888 8889 13133

# Run the collector
CMD ["--config=/etc/otelcol-contrib/config.yaml"]

