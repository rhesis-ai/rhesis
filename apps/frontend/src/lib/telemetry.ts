/**
 * OpenTelemetry instrumentation for Rhesis frontend.
 *
 * This module provides conditional telemetry export based on user preferences.
 */

import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';

let telemetryEnabled = false;
const _provider: WebTracerProvider | null = null;
const tracer: any = null;

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
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    // Return first 16 characters (matches backend)
    return hashHex.substring(0, 16);
  } catch (error) {
    console.error('Error hashing string:', error);
    return '';
  }
}

export function initTelemetry() {
  // Client-side telemetry is intentionally disabled
  // No-op: frontend telemetry not configured
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

  span.setAttribute('deployment.type', 'unknown');

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

  span.setAttribute('deployment.type', 'unknown');

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

  span.setAttribute('deployment.type', 'unknown');

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

  span.setAttribute('deployment.type', 'unknown');

  span.end();
}
