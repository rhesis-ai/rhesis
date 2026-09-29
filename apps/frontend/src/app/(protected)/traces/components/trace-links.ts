/** Link to /traces with the trace drawer open, optionally on one span. */
export function traceDrawerHref({
  traceId,
  projectId,
  spanId,
}: {
  traceId: string;
  projectId: string;
  spanId?: string | null;
}): string {
  const params = new URLSearchParams({
    open_trace: traceId,
    project_id: projectId,
  });
  if (spanId) params.set('open_span', spanId);
  return `/traces?${params.toString()}`;
}
