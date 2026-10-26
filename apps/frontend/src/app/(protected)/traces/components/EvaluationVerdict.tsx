'use client';

import { useState } from 'react';
import { Box, Button, Tooltip, Typography } from '@mui/material';
import { CheckIcon, RateReviewIcon } from '@/components/icons';
import StatusChip from '@/components/common/StatusChip';
import AnnotationIndicator from '@/components/annotations/AnnotationIndicator';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { STATUS_LABEL, type TestResultStatus } from '@/constants/outcomes';
import { useAnnotationMutations } from '@/hooks/useAnnotations';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ANNOTATION_ENTITY_TYPES,
  ENTITY_LEVEL_TARGETS,
} from '@/utils/api-client/interfaces/annotation';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { EntityType } from '@/types/entity-type';
import {
  findStatusByCategory,
  isPassedStatusName,
} from '@/utils/test-result-status';

/** Saved as the comment of a one-click agreement, so the record says what happened. */
export const AGREE_COMMENT = 'Agreed with the automated result.';

interface EvaluationVerdictProps {
  span: SpanNode;
  /** The automated result: the test result's status, else the span's own metrics. */
  status: TestResultStatus | null;
  /** "2 of 3 checks passed", or null when nothing was checked. */
  summary: string | null;
  onAnnotate?: () => void;
  onChanged: () => void;
}

/**
 * The summary line of the Evaluation tab, as on the test run's: the automated
 * result and its tally, then the human verdict with the two ways to record one.
 */
export default function EvaluationVerdict({
  span,
  status,
  summary,
  onAnnotate,
  onChanged,
}: EvaluationVerdictProps) {
  const canCreate = useCan(Capability.Annotation.CREATE);
  const [agreeing, setAgreeing] = useState(false);
  const { create } = useAnnotationMutations(
    ANNOTATION_ENTITY_TYPES.TRACE,
    span.id,
    { parentInvalidate: onChanged }
  );

  const last = span.last_annotation;
  const human =
    last?.status?.name &&
    last.target_type === ENTITY_LEVEL_TARGETS[ANNOTATION_ENTITY_TYPES.TRACE]
      ? last
      : null;
  // Only a pass or a fail can be agreed with; an error or inconclusive result has no verdict.
  const agreeable = status === 'Pass' || status === 'Fail';

  const handleAgree = async () => {
    if (!agreeable) return;
    setAgreeing(true);
    try {
      // Trace annotations take test-result statuses, the same set the annotation form offers.
      const statuses = await new ApiClientFactory()
        .getStatusClient()
        .getStatuses({ entity_type: EntityType.TEST_RESULT });
      const match = findStatusByCategory(
        statuses,
        status === 'Pass' ? 'passed' : 'failed'
      );
      if (!match) return;
      await create({ statusId: String(match.id), comments: AGREE_COMMENT });
    } catch (err) {
      console.error('Failed to save agreement:', err);
    } finally {
      setAgreeing(false);
    }
  };

  return (
    <Box
      sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}
    >
      {status ? (
        <StatusChip
          status={status}
          label={STATUS_LABEL[status]}
          size="small"
          variant="filled"
        />
      ) : (
        <Typography variant="body2" color="text.secondary">
          Not evaluated
        </Typography>
      )}
      {summary && (
        <Typography variant="body2" color="text.secondary">
          {summary}
        </Typography>
      )}
      <Box sx={{ flex: 1 }} />
      <Typography variant="caption" color="text.secondary">
        {human ? 'Human:' : 'Not annotated'}
      </Typography>
      {human?.status?.name && (
        <AnnotationIndicator
          verdict={isPassedStatusName(human.status.name) ? 'passed' : 'failed'}
          hasConflict={span.matches_annotation === false}
          annotator={human.user?.name}
          comment={human.comments}
        />
      )}
      {canCreate && agreeable && !human && (
        <Tooltip
          title={`Record a human verdict of ${STATUS_LABEL[status].toLowerCase()}`}
        >
          <span>
            <Button
              size="small"
              variant="outlined"
              startIcon={<CheckIcon />}
              onClick={handleAgree}
              disabled={agreeing}
              sx={{ textTransform: 'none', py: 0.25 }}
            >
              Agree
            </Button>
          </span>
        </Tooltip>
      )}
      {canCreate && onAnnotate && (
        <Button
          size="small"
          variant="outlined"
          startIcon={<RateReviewIcon />}
          onClick={onAnnotate}
          sx={{ textTransform: 'none', py: 0.25 }}
        >
          Annotate
        </Button>
      )}
    </Box>
  );
}
