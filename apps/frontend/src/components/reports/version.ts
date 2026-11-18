/** A run's endpoint version as one short line, or undefined when it has none. */
export function versionLabel(
  versionInfo: Record<string, unknown> | null | undefined
): string | undefined {
  if (!versionInfo) return undefined;
  const parts = Object.entries(versionInfo)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) =>
      typeof value === 'object' ? `${key}: …` : `${key}: ${String(value)}`
    );
  return parts.length ? parts.join(' · ') : undefined;
}
