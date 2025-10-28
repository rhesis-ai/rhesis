/**
 * OpenTelemetry instrumentation for Rhesis frontend.
 *
 * This module provides conditional telemetry export based on user preferences.
 */

import {
  WebTracerProvider,
  BatchSpanProcessor,
} from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from '@opentelemetry/semantic-conventions';

let telemetryEnabled = false;
let provider: WebTracerProvider | null = null;
let tracer: any = null;

/**
 * Hash a string for privacy using SHA-256 (matches backend implementation).
 *
 * This ensures consistent hashing across frontend and backend for cross-service correlation.
 *
 * Backend implementation (Python):
 * ```python
 * hashlib.sha256(id_str.encode()).hexdigest()[:16]
 * ```
 *
 * @param str String to hash (typically user ID or organization ID)
 * @returns First 16 characters of SHA-256 hex digest
 */
async function hashString(str: string): Promise<string> {
  if (!str) return '';

  try {
    // Use Web Crypto API (available in all modern browsers)
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);

    // Convert buffer to hex string
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

    // Return first 16 characters (matches backend)
    return hashHex.substring(0, 16);
  } catch (error) {
    console.error('Error hashing string:', error);
    return '';
  }
}

/**
 * Initialize OpenTelemetry for the frontend.
 *
 * This should be called once when the app starts.
 */
export function initTelemetry() {
  const otlpEndpoint = process.env.NEXT_PUBLIC_OTEL_ENDPOINT;

  if (!otlpEndpoint) {
    console.log('Telemetry disabled: NEXT_PUBLIC_OTEL_ENDPOINT not set');
    return;
  }

  const deploymentType = process.env.NEXT_PUBLIC_DEPLOYMENT_TYPE || 'unknown';
  const appVersion = process.env.APP_VERSION || 'unknown';

  // Create resource
  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: 'rhesis-frontend',
    [ATTR_SERVICE_VERSION]: appVersion,
    'deployment.type': deploymentType,
    'service.namespace': 'rhesis',
  });

  // Create OTLP exporter
  const exporter = new OTLPTraceExporter({
    url: `${otlpEndpoint}/v1/traces`,
    headers: {},
    // 5 second timeout - don't block app if telemetry is slow
    timeoutMillis: 5000,
  });

  // Create provider with batch processor
  provider = new WebTracerProvider({
    resource,
    spanProcessors: [new BatchSpanProcessor(exporter)],
  });

  // Register provider
  provider.register();

  // Get tracer
  tracer = provider.getTracer('rhesis-frontend', appVersion);

  console.log('Telemetry initialized:', { otlpEndpoint, deploymentType });
}

/**
 * Enable or disable telemetry.
 *
 * @param enabled Whether telemetry is enabled
 */
export function setTelemetryEnabled(enabled: boolean) {
  telemetryEnabled = enabled;
}

/**
 * Check if telemetry is enabled.
 */
export function isTelemetryEnabled(): boolean {
  return telemetryEnabled;
}

/**
 * Track a page view.
 *
 * @param page Page path
 * @param userId User ID (will be hashed with SHA-256)
 * @param organizationId Organization ID (will be hashed with SHA-256)
 */
export async function trackPageView(
  page: string,
  userId?: string,
  organizationId?: string
) {
  if (!telemetryEnabled || !tracer) return;

  const span = tracer.startSpan('page.view');

  span.setAttribute('event.category', 'feature_usage');
  span.setAttribute('feature.name', 'page_view');
  span.setAttribute('feature.action', 'viewed');
  span.setAttribute('page.path', page);

  if (userId) {
    const hashedUserId = await hashString(userId);
    span.setAttribute('user.id', hashedUserId);
  }

  if (organizationId) {
    const hashedOrgId = await hashString(organizationId);
    span.setAttribute('organization.id', hashedOrgId);
  }

  const deploymentType = process.env.NEXT_PUBLIC_DEPLOYMENT_TYPE || 'unknown';
  span.setAttribute('deployment.type', deploymentType);

  span.end();
}

/**
 * Track a user action/event.
 *
 * @param eventName Name of the event
 * @param properties Additional properties
 * @param userId User ID (will be hashed with SHA-256)
 * @param organizationId Organization ID (will be hashed with SHA-256)
 */
export async function trackEvent(
  eventName: string,
  properties: Record<string, string | number | boolean> = {},
  userId?: string,
  organizationId?: string
) {
  if (!telemetryEnabled || !tracer) return;

  const span = tracer.startSpan(eventName);

  span.setAttribute('event.category', 'feature_usage');
  span.setAttribute('feature.name', eventName);
  span.setAttribute('feature.action', 'triggered');

  // Add properties as attributes
  Object.entries(properties).forEach(([key, value]) => {
    span.setAttribute(`metadata.${key}`, String(value));
  });

  if (userId) {
    const hashedUserId = await hashString(userId);
    span.setAttribute('user.id', hashedUserId);
  }

  if (organizationId) {
    const hashedOrgId = await hashString(organizationId);
    span.setAttribute('organization.id', hashedOrgId);
  }

  const deploymentType = process.env.NEXT_PUBLIC_DEPLOYMENT_TYPE || 'unknown';
  span.setAttribute('deployment.type', deploymentType);

  span.end();
}

/**
 * Track a feature usage.
 *
 * @param featureName Name of the feature
 * @param action Action performed
 * @param metadata Additional metadata
 * @param userId User ID (will be hashed with SHA-256)
 * @param organizationId Organization ID (will be hashed with SHA-256)
 */
export async function trackFeatureUsage(
  featureName: string,
  action: string,
  metadata: Record<string, string | number | boolean> = {},
  userId?: string,
  organizationId?: string
) {
  if (!telemetryEnabled || !tracer) return;

  const span = tracer.startSpan(`feature.${featureName}`);

  span.setAttribute('event.category', 'feature_usage');
  span.setAttribute('feature.name', featureName);
  span.setAttribute('feature.action', action);

  // Add metadata as attributes
  Object.entries(metadata).forEach(([key, value]) => {
    span.setAttribute(`metadata.${key}`, String(value));
  });

  if (userId) {
    const hashedUserId = await hashString(userId);
    span.setAttribute('user.id', hashedUserId);
  }

  if (organizationId) {
    const hashedOrgId = await hashString(organizationId);
    span.setAttribute('organization.id', hashedOrgId);
  }

  const deploymentType = process.env.NEXT_PUBLIC_DEPLOYMENT_TYPE || 'unknown';
  span.setAttribute('deployment.type', deploymentType);

  span.end();
}

/**
 * Track user login.
 *
 * @param userId User ID (will be hashed with SHA-256)
 * @param organizationId Organization ID (will be hashed with SHA-256)
 */
export async function trackUserLogin(userId: string, organizationId?: string) {
  if (!telemetryEnabled || !tracer) return;

  const span = tracer.startSpan('user.login');

  span.setAttribute('event.category', 'user_activity');
  span.setAttribute('event.type', 'login');

  const hashedUserId = await hashString(userId);
  span.setAttribute('user.id', hashedUserId);

  if (organizationId) {
    const hashedOrgId = await hashString(organizationId);
    span.setAttribute('organization.id', hashedOrgId);
  }

  const deploymentType = process.env.NEXT_PUBLIC_DEPLOYMENT_TYPE || 'unknown';
  span.setAttribute('deployment.type', deploymentType);

  span.end();
}
