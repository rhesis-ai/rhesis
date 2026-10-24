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
