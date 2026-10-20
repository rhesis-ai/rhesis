'use client';

import React from 'react';
import { Box, Chip, Paper, Typography, useTheme } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import RemoveIcon from '@mui/icons-material/Remove';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import {
  countChecks,
  turnScopeLabel,
  type ResultCheck,
  type ResultCheckGroup,
} from '@/utils/result-checks';

function VerdictIcon({ passed }: { passed: boolean | null }) {
  const theme = useTheme();
  const sx = { fontSize: theme.spacing(2.5), mt: 0.25, flexShrink: 0 };
  if (passed === null) {
    return <RemoveIcon aria-label="Not scored" color="disabled" sx={sx} />;
  }
  return passed ? (
    <CheckIcon aria-label="Passed" color="success" sx={sx} />
  ) : (
    <CloseIcon aria-label="Failed" color="error" sx={sx} />
  );
}

function scoreText(check: ResultCheck): string | undefined {
  const { score, threshold } = check.result ?? {};
  if (typeof score !== 'number' || typeof threshold !== 'number') {
    return undefined;
  }
  return `Score ${score.toFixed(2)} · threshold ${threshold.toFixed(2)}`;
}

function CheckRow({
  check,
  turnCount,
  actions,
}: {
  check: ResultCheck;
  turnCount?: number;
  actions?: React.ReactNode;
}) {
  const scope = turnCount
    ? turnScopeLabel(check.relevantTurns, turnCount)
    : undefined;
  const score = scoreText(check);
  return (
    <Box sx={{ display: 'flex', gap: 1.5, px: 2.25, py: 1.5 }}>
      <VerdictIcon passed={check.passed} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 1,
          }}
        >
          <Typography variant="body2" fontWeight={500}>
            {check.label}
          </Typography>
          {scope && <Chip label={scope} size="small" variant="outlined" />}
          {check.passed === null && (
            <Chip label="Not scored" size="small" variant="outlined" />
          )}
          {score && (
            <Typography variant="caption" color="text.secondary">
              {score}
            </Typography>
          )}
          <Box sx={{ flexGrow: 1 }} />
          {actions}
        </Box>
        {check.reason && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5, wordBreak: 'break-word' }}
          >
            {check.reason}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  const theme = useTheme();
  return (
    <Typography
      variant="caption"
      component="h4"
      color="text.secondary"
      sx={{
        display: 'block',
        px: 2.25,
        pt: 1.5,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: theme.typography.overline.letterSpacing,
      }}
    >
      {children}
    </Typography>
  );
}

interface ResultCheckCardProps {
  group: ResultCheckGroup;
  /** Turns in the conversation; with it, checks get a tag naming the turns they cite. */
  turnCount?: number;
  headerActions?: React.ReactNode;
  rowActions?: (check: ResultCheck) => React.ReactNode;
  footer?: React.ReactNode;
  /** Drops the shadow, for cards sitting inside another panel. */
  flat?: boolean;
}

/** One group of checks: the test's own must do / must not do, or a set of metrics. */
export default function ResultCheckCard({
  group,
  turnCount,
  headerActions,
  rowActions,
  footer,
  flat = false,
}: ResultCheckCardProps) {
  const { passed, total } = countChecks(group.checks);
  // Criteria split by kind; a group of whole metrics has no kind and stays one list.
  const hasKinds = group.checks.some(c => c.kind);
  const mustDo = group.checks.filter(c => c.kind !== 'prohibited');
  const mustNotDo = group.checks.filter(c => c.kind === 'prohibited');

  const rowsFor = (checks: ResultCheck[]) =>
    checks.map(check => (
      <CheckRow
        key={check.key}
        check={check}
        turnCount={turnCount}
        actions={rowActions?.(check)}
      />
    ));

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: BORDER_RADIUS.md,
        borderColor: 'divider',
        boxShadow: flat ? 'none' : ELEVATION.xs,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.25,
          px: 2.25,
          py: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="subtitle1" component="h3" fontWeight={600}>
          {group.title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {`${passed} of ${total} passed`}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        {headerActions}
      </Box>
      {hasKinds ? (
        <>
          {mustDo.length > 0 && <SubHeading>Must do</SubHeading>}
          {rowsFor(mustDo)}
          {mustNotDo.length > 0 && <SubHeading>Must not do</SubHeading>}
          {rowsFor(mustNotDo)}
        </>
      ) : (
        rowsFor(group.checks)
      )}
      {footer}
    </Paper>
  );
}
