FROM otel/opentelemetry-collector-contrib:0.97.0

# Copy custom configuration
COPY otel-collector-config.yaml /etc/otelcol-contrib/config.yaml

# Expose ports
EXPOSE 4317 4318 13133 8889

# Use the default entrypoint from the base image
# It will automatically use /etc/otelcol-contrib/config.yaml

