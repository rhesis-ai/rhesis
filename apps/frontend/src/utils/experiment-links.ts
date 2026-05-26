export function experimentHref(
  experimentId: string,
  version?: string | null
): string {
  const base = `/experiments/${experimentId}`;
  return version ? `${base}?version=${encodeURIComponent(version)}` : base;
}
