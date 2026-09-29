import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

/** Root-to-span path for `spanId`, or null when the trace has no such span. */
export function findSpanPath(
  spans: SpanNode[],
  spanId: string
): SpanNode[] | null {
  for (const span of spans) {
    if (span.span_id === spanId) return [span];
    const childPath = findSpanPath(span.children ?? [], spanId);
    if (childPath) return [span, ...childPath];
  }
  return null;
}

/** Index of the Tree tab: the Conversation tab comes first when present. */
export function treeTabIndex(hasConversation: boolean): number {
  return hasConversation ? 1 : 0;
}

export interface InitialSelection {
  span: SpanNode | null;
  openTree: boolean;
}

/**
 * Which span the drawer selects after loading a trace. A span id wins over a
 * turn index, since the span already sits under its own turn's root. An
 * unknown span id falls back to the turn index, then to the first root.
 */
export function pickInitialSelection(
  trace: Pick<TraceDetailResponse, 'root_spans'>,
  {
    initialSpanId,
    initialTurnIndex,
  }: { initialSpanId?: string; initialTurnIndex?: number }
): InitialSelection {
  const roots = trace.root_spans;
  if (roots.length === 0) return { span: null, openTree: false };

  const path = initialSpanId ? findSpanPath(roots, initialSpanId) : null;
  if (path) return { span: path[path.length - 1], openTree: true };

  if (initialTurnIndex !== undefined) {
    const index = Math.min(Math.max(initialTurnIndex, 0), roots.length - 1);
    return { span: roots[index], openTree: true };
  }
  return { span: roots[0], openTree: false };
}
