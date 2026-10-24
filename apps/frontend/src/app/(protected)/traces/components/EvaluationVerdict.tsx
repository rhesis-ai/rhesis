'use client';

import { useState } from 'react';
import { Box, Button, Tooltip, Typography } from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme';
import { CheckIcon, RateReviewIcon } from '@/components/icons';
import StatusChip from '@/components/common/StatusChip';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
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
import { automatedVerdictFor } from './trace-verdict';

/** Saved as the comment of a one-click agreement, so the record says what happened. */
export const AGREE_COMMENT = 'Agreed with the automated result.';

interface EvaluationVerdictProps {
  span: SpanNode;
  onAnnotate?: () => void;
  onChanged: () => void;
}

const sideLabelSx = {
  fontWeight: 600,
  textTransform: 'uppercase',
  color: 'text.secondary',
} as const;

/**
 * The automated result beside the human one, with the two ways to record a
 * human verdict: agree in one click, or open the annotation form.
 */
export default function EvaluationVerdict({
  span,
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

  const automated = automatedVerdictFor(span);
  const last = span.last_annotation;
  const human =
    last?.status?.name &&
    last.target_type === ENTITY_LEVEL_TARGETS[ANNOTATION_ENTITY_TYPES.TRACE]
      ? last
      : null;
  const conflict = !!human && span.matches_annotation === false;

  const handleAgree = async () => {
    if (!automated) return;
    setAgreeing(true);
    try {
      // Trace annotations take test-result statuses, the same set the annotation form offers.
      const statuses = await new ApiClientFactory()
        .getStatusClient()
        .getStatuses({ entity_type: EntityType.TEST_RESULT });
      const status = findStatusByCategory(
        statuses,
        automated.passed ? 'passed' : 'failed'
      );
      if (!status) return;
      await create({ statusId: String(status.id), comments: AGREE_COMMENT });
    } catch (err) {
      console.error('Failed to save agreement:', err);
    } finally {
      setAgreeing(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        border: 1,
        borderColor: conflict ? 'warning.main' : 'divider',
        borderRadius: BORDER_RADIUS.sm,
      }}
    >
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          px: 1.75,
          py: 1.25,
          borderRight: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="caption" component="p" sx={sideLabelSx}>
          Automated
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
          {automated ? (
            <>
              <StatusChip
                passed={automated.passed}
                label={automated.label}
                size="small"
                variant="filled"
              />
              <Typography variant="caption" color="text.secondary">
                {automated.count} metrics passed
              </Typography>
            </>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Not evaluated
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ flex: 1, minWidth: 0, px: 1.75, py: 1.25 }}>
        <Typography variant="caption" component="p" sx={sideLabelSx}>
          Human
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
          {human?.status?.name ? (
            <>
              <StatusChip
                passed={isPassedStatusName(human.status.name)}
                label={
                  isPassedStatusName(human.status.name) ? 'Passed' : 'Failed'
                }
                size="small"
                variant="outlined"
              />
              <Typography variant="caption" color="text.secondary" noWrap>
                {human.user?.name ? `by ${human.user.name}` : ''}
                {conflict ? ' · disagrees with automated' : ''}
              </Typography>
            </>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Not annotated
            </Typography>
          )}
          <Box sx={{ flex: 1 }} />
          {canCreate && automated && !human && (
            <Tooltip
              title={`Record a human verdict of ${automated.label.toLowerCase()}`}
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
      </Box>
    </Box>
  );
}
