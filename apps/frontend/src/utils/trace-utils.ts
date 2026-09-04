/**
 * Utility functions for trace visualization and formatting
 */

import { SpanNode } from './api-client/interfaces/telemetry';
import { formatDate } from './date';

/**
 * Format duration for display in table (shorter format)
 * Uses shorter decimals for compact display
 */
export function formatDurationShort(ms: number): string {
  if (ms < 1) {
    return `${(ms * 1000).toFixed(0)}μs`;
  }
  if (ms < 1000) {
    return `${ms.toFixed(0)}ms`;
  }
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${(ms / 60000).toFixed(1)}min`;
}

/**
 * Get color for environment badge
 * Returns Material-UI compatible color
 */
export function getEnvironmentColor(
  environment: string
):
  | 'error'
  | 'warning'
  | 'default'
  | 'primary'
  | 'secondary'
  | 'info'
  | 'success' {
  switch (environment?.toLowerCase()) {
    case 'production':
      return 'error';
    case 'staging':
      return 'warning';
    case 'development':
      return 'info';
    default:
      return 'default';
  }
}

/**
 * Truncate trace ID for display
 * Shows first 8 and last 8 characters with ellipsis in middle
 */
export function truncateTraceId(traceId: string): string {
  if (!traceId || traceId.length <= 20) {
    return traceId;
  }
  return `${traceId.slice(0, 8)}...${traceId.slice(-8)}`;
}

/**
 * Truncate span ID for display
 * Shows first 8 and last 4 characters with ellipsis
 */
export function truncateSpanId(spanId: string): string {
  if (!spanId || spanId.length <= 16) {
    return spanId;
  }
  return `${spanId.slice(0, 8)}...${spanId.slice(-4)}`;
}

/**
 * Format cost for display
 * Uses appropriate precision based on magnitude
 */
export function formatCost(costUsd: number): string {
  if (costUsd === 0) {
    return '$0.00';
  }
  if (costUsd < 0.001) {
    return `$${costUsd.toFixed(6)}`;
  }
  if (costUsd < 0.01) {
    return `$${costUsd.toFixed(4)}`;
  }
  return `$${costUsd.toFixed(2)}`;
}

/**
 * Format token count with thousands separator
 */
export function formatTokenCount(tokens: number): string {
  return tokens.toLocaleString();
}

export interface SpanUsage {
  input: number;
  output: number;
  total: number;
  costUsd: number | null;
}

/**
 * Token counts and cost for one span, or null when it has neither.
 *
 * Tokens come off the raw span attributes; cost comes from `cost_usd`, which the
 * backend fills in from the enrichment breakdown -- the attributes never carry a
 * price. Most spans (tool calls, function spans) have neither, and an empty
 * "Usage" block on every span is noise, hence the null.
 */
export function spanUsage(span: SpanNode): SpanUsage | null {
  const attrs = span.attributes ?? {};
  const asCount = (value: unknown): number => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  };

  const input = asCount(attrs['ai.llm.tokens.input']);
  const output = asCount(attrs['ai.llm.tokens.output']);
  // Reported rather than derived: Google ADK folds cache-read tokens into its
  // total, so input + output can fall short of it.
  const reportedTotal = asCount(attrs['ai.llm.tokens.total']);
  const total = reportedTotal > 0 ? reportedTotal : input + output;
  const costUsd =
    typeof span.cost_usd === 'number' && span.cost_usd > 0
      ? span.cost_usd
      : null;

  if (total === 0 && costUsd === null) {
    return null;
  }

  return { input, output, total, costUsd };
}

/**
 * Input/output tokens as two separate figures, deliberately not presented as a
 * breakdown of the total: Google ADK folds cache-read tokens into the total it
 * reports, so input + output legitimately falls short of it.
 *
 * Returns undefined when neither figure is known, so the caller renders no
 * tooltip rather than an empty one.
 */
export function tokenSplitLabel(
  inputTokens: number | null | undefined,
  outputTokens: number | null | undefined
): string | undefined {
  const input = inputTokens ?? 0;
  const output = outputTokens ?? 0;
  if (input === 0 && output === 0) {
    return undefined;
  }
  return `${formatTokenCount(input)} input \u00b7 ${formatTokenCount(output)} output`;
}

/**
 * Get span type from span name
 * Returns human-readable type label
 */
export function getSpanType(spanName: string): string {
  if (!spanName) return 'Other';
  if (spanName.includes('ai.llm.invoke')) return 'LLM';
  if (spanName.includes('function.')) return 'Function';
  if (spanName.includes('db.')) return 'Database';
  if (spanName.includes('http.')) return 'HTTP';
  return 'Other';
}

/**
 * Extract operation name from full span name
 * Example: "function.chat" -> "chat"
 */
export function extractOperationName(spanName: string): string {
  if (!spanName) return '';
  const parts = spanName.split('.');
  return parts[parts.length - 1] || spanName;
}

/**
 * Calculate percentage of parent duration
 */
export function calculateDurationPercentage(
  spanDuration: number,
  parentDuration: number
): number {
  if (parentDuration === 0) return 0;
  return (spanDuration / parentDuration) * 100;
}

/**
 * Check if span is a leaf node (no children)
 */
export function isLeafSpan(span: SpanNode | { children?: unknown[] }): boolean {
  return !span.children || span.children.length === 0;
}

/**
 * Count total spans in tree (including children)
 */
export function countSpansInTree(spans: SpanNode[]): number {
  let count = 0;

  function countRecursive(span: SpanNode) {
    count++;
    if (span.children) {
      span.children.forEach(countRecursive);
    }
  }

  spans.forEach(countRecursive);
  return count;
}

/**
 * Get depth of span tree
 */
export function getTreeDepth(spans: SpanNode[]): number {
  function getDepthRecursive(span: SpanNode, depth: number): number {
    if (!span.children || span.children.length === 0) {
      return depth;
    }

    const childDepths = span.children.map(child =>
      getDepthRecursive(child, depth + 1)
    );

    return Math.max(...childDepths);
  }

  if (spans.length === 0) return 0;

  const depths = spans.map(span => getDepthRecursive(span, 1));
  return Math.max(...depths);
}

/**
 * Format ISO date to locale string
 */
export function formatTraceDate(isoDate: string): string {
  if (!isoDate) return '';
  return formatDate(isoDate);
}

/**
 * Get status chip props
 * Returns consistent chip styling for status codes
 */
export function getStatusChipProps(statusCode: string): {
  label: string;
  color: 'success' | 'error' | 'warning' | 'default';
  variant: 'filled' | 'outlined';
} {
  if (statusCode === 'OK') {
    return {
      label: 'OK',
      color: 'success',
      variant: 'outlined',
    };
  }

  if (statusCode === 'ERROR') {
    return {
      label: 'ERROR',
      color: 'error',
      variant: 'filled',
    };
  }

  return {
    label: statusCode,
    color: 'default',
    variant: 'outlined',
  };
}
