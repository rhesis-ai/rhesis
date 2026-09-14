'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import AnnotationsPanel from '@/components/annotations/AnnotationsPanel';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isPassedStatusName } from '@/utils/test-result-status';
import { ANNOTATION_ENTITY_TYPES } from '@/utils/api-client/interfaces/annotation';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';
import type { MentionOption } from '@/components/common/MentionTextInput';
import TraceReviewDrawer from './TraceReviewDrawer';

interface TraceAnnotationsTabProps {
  selectedSpan: SpanNode;
  trace: TraceDetailResponse;
  onTraceUpdated: () => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
}

type MetricEntry = {
  is_successful?: boolean;
  override?: { original_value?: boolean };
};

/**
 * The automated verdict for a span, counted across both metric sections.
 *
 * Deliberately the automated result and not the span's current outcome: it
 * sits beside the human verdict so the difference is visible, and
 * `displayStatusOf` already folds the annotation in, which would make the two
 * sides always agree. Each metric is read at `override.original_value` when an
 * annotation has already flipped it.
 */
function automatedVerdictFor(span: SpanNode) {
  const traceMetrics = span.trace_metrics as Record<
    string,
    Record<string, unknown>
  > | null;
  if (!traceMetrics) return { passed: false, label: 'N/A', count: '0/0' };

  let total = 0;
  let passed = 0;
  for (const section of ['turn_metrics', 'conversation_metrics']) {
    const sectionData = traceMetrics[section] as
      | Record<string, unknown>
      | undefined;
    const metrics = (sectionData?.metrics ?? {}) as Record<string, MetricEntry>;
    for (const metric of Object.values(metrics)) {
      total++;
      if (metric.override?.original_value ?? metric.is_successful) passed++;
    }
  }

  const allPassed = total > 0 && passed === total;
  return {
    passed: allPassed,
    label: allPassed ? 'Passed' : 'Failed',
    count: `${passed}/${total}`,
  };
}

/**
 * The annotations tab for a trace span: works out the automated verdict and
 * owns the create drawer, then hands the list to the shared panel.
 */
export default function TraceAnnotationsTab({
  selectedSpan,
  trace: _trace,
  onTraceUpdated,
  mentionableMetrics = [],
  mentionableTurns = [],
  initialComment = '',
  initialStatus,
  onCommentUsed,
}: TraceAnnotationsTabProps) {
  const { data: session } = useSession();
  const canCreate = useCan(Capability.Annotation.CREATE);
  const [createOpen, setCreateOpen] = useState(false);

  const pendingCommentRef = useRef<{
    comment: string;
    status?: 'passed' | 'failed';
  } | null>(null);

  useEffect(() => {
    if (!initialComment) return;
    pendingCommentRef.current = { comment: initialComment, status: initialStatus };
    setCreateOpen(true);
    onCommentUsed?.();
  }, [initialComment, initialStatus, onCommentUsed]);

  const automatedStatus = useMemo(
    () => automatedVerdictFor(selectedSpan),
    [selectedSpan]
  );

  // Traces snapshot original_status_id from the first annotation onward, so
  // matches_annotation is authoritative; before that there is nothing to
  // conflict with.
  const last = selectedSpan.last_annotation;
  const hasConflict =
    !!last?.status?.name &&
    selectedSpan.matches_annotation === false &&
    isPassedStatusName(last.status.name) !== automatedStatus.passed;

  return (
    <>
      <AnnotationsPanel
        entityType={ANNOTATION_ENTITY_TYPES.TRACE}
        entityId={selectedSpan.id}
        automatedStatus={automatedStatus}
        currentUserId={session?.user?.id ?? ''}
        hasConflict={hasConflict}
        onCreate={canCreate ? () => setCreateOpen(true) : undefined}
        onChanged={onTraceUpdated}
      />
      <TraceReviewDrawer
        open={createOpen}
        onClose={() => {
          pendingCommentRef.current = null;
          setCreateOpen(false);
        }}
        selectedSpan={selectedSpan}
        onSave={async () => onTraceUpdated()}
        initialComment={pendingCommentRef.current?.comment}
        initialStatus={pendingCommentRef.current?.status}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
      />
    </>
  );
}
