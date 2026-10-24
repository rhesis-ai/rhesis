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
import TraceAnnotationDrawer from './TraceAnnotationDrawer';
import { automatedVerdictFor } from './trace-verdict';

interface TraceAnnotationsTabProps {
  selectedSpan: SpanNode;
  trace: TraceDetailResponse;
  onTraceUpdated: () => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
  /** Passed to the panel: the parent already shows both verdicts. */
  compact?: boolean;
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
  compact = false,
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
    pendingCommentRef.current = {
      comment: initialComment,
      status: initialStatus,
    };
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
    !!automatedStatus &&
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
        compact={compact}
      />
      <TraceAnnotationDrawer
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
