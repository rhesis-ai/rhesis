'use client';

import React, { useEffect, useState } from 'react';
import { Box, Button, Link, Paper, Typography, useTheme } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import RemoveIcon from '@mui/icons-material/Remove';
import StatusChip from '@/components/common/StatusChip';
import { STATUS_LABEL, type TestResultStatus } from '@/constants/outcomes';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import {
  checksSummary,
  turnScopeLabel,
  type ResultCheck,
  type ResultCheckGroup,
} from '@/utils/result-checks';

interface ConversationResultProps {
  groups: ResultCheckGroup[];
  /** Omitted when nothing was scored, rather than claiming a pass. */
  status?: TestResultStatus;
  turnCount: number;
  onShowEvaluation?: () => void;
  /** Whether a person has already annotated the result. */
  reviewed: boolean;
  /** Whether that annotation agrees with the automated verdict. */
  reviewMatches: boolean;
  reviewerName?: string;
  onConfirm?: () => void;
  onOverride?: () => void;
  isConfirming?: boolean;
  onUndo?: () => void;
  isUndoing?: boolean;
}

function CheckLine({
  check,
  turnCount,
}: {
  check: ResultCheck;
  turnCount: number;
}) {
  const theme = useTheme();
  const failed = check.passed === false;
  const iconSx = { fontSize: theme.spacing(2.25), flexShrink: 0 };
  const turns =
    turnScopeLabel(check.relevantTurns, turnCount) ??
    (check.relevantTurns.length > 0 ? 'All turns' : undefined);
  return (
    <Box
      component="li"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        py: 1.25,
        borderBottom: 1,
        borderColor: 'divider',
        '&:last-of-type': { borderBottom: 0 },
      }}
    >
      {check.passed === null ? (
        <RemoveIcon aria-label="Not scored" color="disabled" sx={iconSx} />
      ) : failed ? (
        <CloseIcon aria-label="Failed" color="error" sx={iconSx} />
      ) : (
        <CheckIcon aria-label="Passed" color="success" sx={iconSx} />
      )}
      <Typography
        variant="body2"
        sx={{ flex: 1, minWidth: 0, fontWeight: failed ? 500 : 400 }}
      >
        {check.label}
      </Typography>
      {turns && (
        <Typography
          variant="caption"
          color={failed ? 'error.main' : 'text.secondary'}
          sx={{ whiteSpace: 'nowrap' }}
        >
          {turns}
        </Typography>
      )}
    </Box>
  );
}

/** The review step, kept apart from the verdict so a button never reads as a result. */
function ReviewFooter({
  reviewed,
  reviewMatches,
  reviewerName,
  onConfirm,
  onOverride,
  isConfirming,
  onUndo,
  isUndoing,
}: Pick<
  ConversationResultProps,
  | 'reviewed'
  | 'reviewMatches'
  | 'reviewerName'
  | 'onConfirm'
  | 'onOverride'
  | 'isConfirming'
  | 'onUndo'
  | 'isUndoing'
>) {
  const by = reviewerName ? ` by ${reviewerName}` : '';
  const text = !reviewed
    ? 'Automated verdict · not reviewed yet'
    : reviewMatches
      ? `Verdict confirmed${by}`
      : `Verdict changed${by}`;
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 2,
        px: 3,
        py: 1.5,
        bgcolor: 'action.hover',
        borderTop: 1,
        borderColor: 'divider',
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {text}
      </Typography>
      {reviewed && onUndo && (
        <Button
          variant="text"
          color="inherit"
          onClick={onUndo}
          disabled={isUndoing}
        >
          Undo
        </Button>
      )}
      {!reviewed && (onConfirm || onOverride) && (
        <Box sx={{ display: 'flex', gap: 1 }}>
          {onOverride && (
            <Button variant="outlined" color="inherit" onClick={onOverride}>
              Override
            </Button>
          )}
          {onConfirm && (
            <Button
              variant="contained"
              onClick={onConfirm}
              disabled={isConfirming}
            >
              Confirm verdict
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
}

/**
 * Closes a conversation: a neutral "ended" divider, then the verdict with every check behind
 * it, then the review step on its own line.
 */
export default function ConversationResult({
  groups,
  status,
  turnCount,
  onShowEvaluation,
  reviewed,
  reviewMatches,
  reviewerName,
  onConfirm,
  onOverride,
  isConfirming = false,
  onUndo,
  isUndoing = false,
}: ConversationResultProps) {
  const checks = groups.flatMap(g => g.checks);
  // A reviewed pass needs no more attention, so it starts as one line.
  const collapsible =
    checks.length > 0 && reviewed && reviewMatches && status === 'Pass';
  const [expanded, setExpanded] = useState(!collapsible);
  // Confirming a pass, or undoing that, lands in the same state as a reload would.
  useEffect(() => {
    setExpanded(!collapsible);
  }, [collapsible]);
  const canReview = !reviewed && (onConfirm || onOverride);
  const hasCard = checks.length > 0 || reviewed || canReview;

  return (
    <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          color: 'text.secondary',
        }}
      >
        <Box aria-hidden sx={{ flex: 1, height: '1px', bgcolor: 'divider' }} />
        <Typography variant="body2" color="text.secondary">
          {`Conversation ended after ${turnCount} ${turnCount === 1 ? 'turn' : 'turns'}`}
        </Typography>
        <Box aria-hidden sx={{ flex: 1, height: '1px', bgcolor: 'divider' }} />
      </Box>

      {hasCard && (
        <Paper
          variant="outlined"
          data-testid="result-summary"
          sx={{
            borderRadius: BORDER_RADIUS.md,
            borderColor: 'divider',
            boxShadow: ELEVATION.xs,
            overflow: 'hidden',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 1.5,
              px: 3,
              py: 2,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 1.5,
              }}
            >
              {status && (
                <StatusChip
                  status={status}
                  label={STATUS_LABEL[status]}
                  size="small"
                  variant="filled"
                />
              )}
              {checks.length > 0 && (
                <Typography variant="body2" fontWeight={500}>
                  {checksSummary(groups)}
                </Typography>
              )}
              {!expanded && reviewerName && (
                <Typography variant="body2" color="text.secondary">
                  {`· Confirmed by ${reviewerName}`}
                </Typography>
              )}
            </Box>
            {expanded
              ? onShowEvaluation && (
                  <Link
                    component="button"
                    type="button"
                    variant="body2"
                    underline="hover"
                    onClick={onShowEvaluation}
                    sx={{ fontWeight: 500 }}
                  >
                    See full evaluation
                  </Link>
                )
              : checks.length > 0 && (
                  <Link
                    component="button"
                    type="button"
                    variant="body2"
                    underline="hover"
                    onClick={() => setExpanded(true)}
                    sx={{ fontWeight: 500 }}
                  >
                    Show checks
                  </Link>
                )}
          </Box>

          {expanded && checks.length > 0 && (
            <Box
              component="ul"
              sx={{
                listStyle: 'none',
                m: 0,
                px: 3,
                py: 0.5,
                borderTop: 1,
                borderColor: 'divider',
              }}
            >
              {checks.map(check => (
                <CheckLine
                  key={check.key}
                  check={check}
                  turnCount={turnCount}
                />
              ))}
            </Box>
          )}

          {expanded && (reviewed || canReview) && (
            <ReviewFooter
              onUndo={onUndo}
              isUndoing={isUndoing}
              reviewed={reviewed}
              reviewMatches={reviewMatches}
              reviewerName={reviewerName}
              onConfirm={onConfirm}
              onOverride={onOverride}
              isConfirming={isConfirming}
            />
          )}
        </Paper>
      )}
    </Box>
  );
}
