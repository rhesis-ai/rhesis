/**
 * Utility function to format duration in milliseconds to human-readable format
 * @param ms Duration in milliseconds
 * @returns Formatted duration string (e.g., "150μs", "2.50ms", "1.23s", "2.50min")
 */
export function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  if (ms < 1000) return `${ms.toFixed(2)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}min`;
}
