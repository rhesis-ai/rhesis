'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ANNOTATION_ENTITY_TYPES } from '@/utils/api-client/interfaces/annotation';
import AnnotationsPanel from '@/components/annotations/AnnotationsPanel';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { hasConflictingAnnotation } from '@/utils/test-result-status';
import type { MentionOption } from '@/components/common/MentionTextInput';
import { getLatestMetricAnnotationForResult } from './test-run-summary-utils';
import ReviewJudgementDrawer from './ReviewJudgementDrawer';

interface TestDetailAnnotationsTabProps {
  test: TestResultDetail;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
}

/**
 * The annotations tab for a test result: works out the automated verdict and
 * owns the create drawer, then hands the list to the shared panel.
 */
export default function TestDetailAnnotationsTab({
  test,
  onTestResultUpdate,
  currentUserId,
  initialComment = '',
  initialStatus,
  onCommentUsed,
  mentionableMetrics = [],
  mentionableTurns = [],
}: TestDetailAnnotationsTabProps) {
  const [createOpen, setCreateOpen] = useState(false);

  // Held in a ref so a parent reset does not clear what the drawer opened with.
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

  /**
   * Each metric is read at its automated value -- `override.original_value`
   * when an annotation already flipped it -- or this would compare the human
   * verdict against a number a human had already moved.
   */
  const automatedStatus = useMemo(() => {
    const metricValues = Object.values(test.test_metrics?.metrics ?? {});
    const passed = metricValues.filter(
      m => m.override?.original_value ?? m.is_successful
    ).length;
    const total = metricValues.length;
    const allPassed = total > 0 && passed === total;
    return {
      passed: allPassed,
      label: allPassed ? 'Passed' : 'Failed',
      count: `${passed}/${total}`,
    };
  }, [test]);

  const metricVerdictLabel =
    getLatestMetricAnnotationForResult(test)?.status?.name ?? null;

  const refreshParent = async () => {
    const updated = await new ApiClientFactory()
      .getTestResultsClient()
      .getTestResult(test.id);
    onTestResultUpdate(updated);
  };

  return (
    <>
      <AnnotationsPanel
        entityType={ANNOTATION_ENTITY_TYPES.TEST_RESULT}
        entityId={test.id}
        automatedStatus={automatedStatus}
        currentUserId={currentUserId}
        hasConflict={hasConflictingAnnotation(test)}
        metricVerdictLabel={metricVerdictLabel}
        onCreate={
          can(test, Capability.Annotation.CREATE)
            ? () => setCreateOpen(true)
            : undefined
        }
        onChanged={() => void refreshParent()}
      />
      <ReviewJudgementDrawer
        open={createOpen}
        onClose={() => {
          pendingCommentRef.current = null;
          setCreateOpen(false);
        }}
        test={test}
        onSave={() => refreshParent()}
        initialComment={pendingCommentRef.current?.comment}
        initialStatus={pendingCommentRef.current?.status}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
      />
    </>
  );
}
