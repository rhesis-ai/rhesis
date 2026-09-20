/**
 * Utility functions for trace visualization and formatting
 */

import type {
  SpanNode,
  TraceMetricsResponse,
} from './api-client/interfaces/telemetry';
import { formatDate } from './date';
import { formatMoney } from './money';

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
  return formatMoney(costUsd);
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
  // Zero is kept: a span enrichment priced at nothing really did cost nothing.
  // A span it could not price carries no cost_usd at all, which is the null.
  const costUsd = typeof span.cost_usd === 'number' ? span.cost_usd : null;

  if (total === 0 && costUsd === null) {
    return null;
  }

  return { input, output, total, costUsd };
}

/**
 * Usage for a span and everything beneath it.
 *
 * Only `ai.llm.invoke` leaves carry token attributes, so a container span on its own
 * reports nothing. Rolling the subtree up is what makes the panel useful: clicking an
 * agent span answers "what did this agent cost", which is the question people are
 * actually asking when they click it.
 *
 * `llmSpanCount` is how many spans in the subtree contributed, so the caller can say
 * where the number came from. It is 0 on a leaf, which is how callers tell a rollup
 * from a span's own usage.
 */
export function subtreeUsage(
  span: SpanNode
): (SpanUsage & { llmSpanCount: number }) | null {
  const own = spanUsage(span);
  let input = own?.input ?? 0;
  let output = own?.output ?? 0;
  let total = own?.total ?? 0;
  let costUsd = own?.costUsd ?? null;
  let llmSpanCount = 0;

  for (const child of span.children ?? []) {
    const below = subtreeUsage(child);
    if (!below) {
      continue;
    }
    input += below.input;
    output += below.output;
    // Summed from each node's own reported total rather than recomputed, so ADK's
    // cache-read tokens survive the rollup.
    total += below.total;
    if (below.costUsd !== null) {
      costUsd = (costUsd ?? 0) + below.costUsd;
    }
    llmSpanCount += below.llmSpanCount + (spanUsage(child) ? 1 : 0);
  }

  if (total === 0 && costUsd === null) {
    return null;
  }

  return { input, output, total, costUsd, llmSpanCount };
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

/**
 * The words every cost card uses, so the traces page and a test run's summary
 * cannot describe the same silence differently. They already had: one offered
 * the documentation link below and a tooltip, the other neither.
 */
export const COSTS_DOC_URL =
  'https://docs.rhesis.ai/docs/tracing/costs#when-a-figure-is-missing';

/** What a cost card shows when nothing on the run could be priced. */
export const NO_COST_DATA = 'No cost data';

/** Shown while enrichment still has traces of the scope to get through. */
export const PRICING_IN_PROGRESS = 'Working out what this cost';

export const NO_COST_DATA_TOOLTIP =
  'Rhesis prices a run from the tokens its LLM calls reported. A model with no ' +
  'published price, such as a self-hosted one, has no cost to show.';

export const COST_TOOLTIP =
  "What this run's traced LLM calls cost, and the tokens behind it. Figures keep " +
  'climbing while enrichment works through the run traces.';

/**
 * Whether a scope has any traced LLM calls to report on.
 *
 * A test run against an endpoint with no instrumentation, or a project before
 * anything has been traced, has no usage rather than usage of zero. Callers
 * hold their tile back entirely rather than offering a confident nothing.
 */
export function hasTracedUsage(usage: TraceMetricsResponse): boolean {
  return usage.total_traces > 0;
}

/**
 * Whether the cost on screen is a figure somebody computed.
 *
 * A scope whose traces were priced and add up to zero really did cost nothing
 * and should say so. One with no priced traces has a zero that means "no idea",
 * and shows tokens instead. `total_cost_usd` alone cannot tell the two apart.
 */
export function isCostKnown(usage: TraceMetricsResponse): boolean {
  return usage.priced_traces > 0;
}

/**
 * Whether enrichment still has traces in this scope to get through.
 *
 * The difference between "no cost yet" and "no cost, ever": the first is worth
 * waiting for, the second is worth explaining.
 */
export function isPricingInProgress(usage: TraceMetricsResponse): boolean {
  return usage.enriched_traces < usage.total_traces;
}
