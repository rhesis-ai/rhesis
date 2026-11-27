/**
 * Utility function to format duration in milliseconds to human-readable format
 * @param ms Duration in milliseconds
 * @returns Formatted duration string (e.g., "150μs", "838ms", "1.23s", "2.50min")
 */
export function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  // Whole milliseconds; 999.6 rounds into the seconds branch rather than reading "1000ms".
  if (Math.round(ms) < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}min`;
}

/** Span attribute marking a span built from what a response reported, not recorded. */
export const SPAN_SOURCE_ATTRIBUTE = 'rhesis.span.source';
export const REPORTED_SPAN_SOURCE = 'reported';
export const NO_TIMING_LABEL = 'No timing';

/** Whether the span was built from a response's reported values, which carry no timing. */
export function isReportedSpan(span: {
  attributes?: Record<string, unknown> | null;
}): boolean {
  return span.attributes?.[SPAN_SOURCE_ATTRIBUTE] === REPORTED_SPAN_SOURCE;
}

/** A span's duration, or "No timing" for a reported span, whose zero is not a measurement. */
export function formatSpanDuration(span: {
  duration_ms: number;
  attributes?: Record<string, unknown> | null;
}): string {
  return isReportedSpan(span)
    ? NO_TIMING_LABEL
    : formatDuration(span.duration_ms);
}
