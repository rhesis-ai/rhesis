'use client';

import React, { useState } from 'react';
import { Box, Chip, Collapse, Tooltip, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { CheckIcon, ChevronRightIcon, CloseIcon } from '@/components/icons';
import RemoveIcon from '@mui/icons-material/Remove';
import {
  countChecks,
  turnScopeLabel,
  type ResultCheck,
} from '@/utils/result-checks';

const overlineSx = (theme: Theme) => ({
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: theme.typography.overline.letterSpacing,
  color: 'text.secondary',
});

function VerdictIcon({ passed }: { passed: boolean | null }) {
  const sx = {
    fontSize: (theme: Theme) => theme.spacing(2),
    mt: 0.25,
    flexShrink: 0,
  };
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
  if (typeof score !== 'number') return undefined;
  return typeof threshold === 'number'
    ? `${score.toFixed(2)} / ${threshold.toFixed(2)}`
    : score.toFixed(2);
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
  // Only failures explain themselves up front; a passing check's reason is a click away.
  const [open, setOpen] = useState(check.passed === false);
  return (
    <Box sx={{ display: 'flex', gap: 1, py: 0.5 }}>
      <VerdictIcon passed={check.passed} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            component="button"
            type="button"
            aria-expanded={check.reason ? open : undefined}
            onClick={() => setOpen(o => !o)}
            disabled={!check.reason}
            sx={{
              p: 0,
              border: 0,
              bgcolor: 'transparent',
              font: 'inherit',
              color: 'text.primary',
              textAlign: 'left',
              cursor: check.reason ? 'pointer' : 'default',
              minWidth: 0,
              overflow: 'hidden',
            }}
          >
            <Typography variant="body2" noWrap title={check.label}>
              {check.label}
            </Typography>
          </Box>
          {scope && (
            <Chip
              label={scope}
              size="small"
              variant="outlined"
              sx={{ height: theme => theme.spacing(2.5) }}
            />
          )}
          {check.passed === null && (
            <Chip
              label="Not scored"
              size="small"
              variant="outlined"
              sx={{ height: theme => theme.spacing(2.5) }}
            />
          )}
          <Box sx={{ flex: 1 }} />
          {score && (
            <Typography
              variant="caption"
              color="text.secondary"
              title="Score / threshold"
              sx={theme => ({
                fontFamily: theme.typography.fontFamilyCode,
                flexShrink: 0,
              })}
            >
              {score}
            </Typography>
          )}
          {actions}
        </Box>
        {check.reason && (
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Typography
              variant="caption"
              component="p"
              color="text.secondary"
              sx={{ mt: 0.25, wordBreak: 'break-word' }}
            >
              {check.reason}
            </Typography>
          </Collapse>
        )}
      </Box>
    </Box>
  );
}

/** A labelled block of text above the checks, e.g. the test's goal. */
export function SectionText({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Box>
      <Typography variant="caption" component="p" sx={overlineSx}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        component="div"
        sx={{ mt: 0.25, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
      >
        {children}
      </Typography>
    </Box>
  );
}

interface CheckSectionProps {
  title: string;
  /** Shown on hovering the title, e.g. the requirement's description. */
  titleHint?: string;
  checks: ResultCheck[];
  /** Turns in the conversation; with it, checks get a tag naming the turns they cite. */
  turnCount?: number;
  intro?: React.ReactNode;
  headerActions?: React.ReactNode;
  rowActions?: (check: ResultCheck) => React.ReactNode;
  footer?: React.ReactNode;
}

/**
 * One group of checks laid out like the test run's evaluation cards, but flat:
 * a title with its tally, what the checks were read from, then one row each.
 */
export default function CheckSection({
  title,
  titleHint,
  checks,
  turnCount,
  intro,
  headerActions,
  rowActions,
  footer,
}: CheckSectionProps) {
  const { passed, total } = countChecks(checks);
  // A group that fully passed folds to its header line; one with a failure starts open.
  const [open, setOpen] = useState(passed < total || total === 0);
  const [showIntro, setShowIntro] = useState(false);
  // Criteria split by kind; a group of whole metrics has no kind and stays one list.
  const hasKinds = checks.some(c => c.kind);
  const mustDo = checks.filter(c => c.kind !== 'prohibited');
  const mustNotDo = checks.filter(c => c.kind === 'prohibited');

  const rows = (list: ResultCheck[]) =>
    list.map(check => (
      <CheckRow
        key={check.key}
        check={check}
        turnCount={turnCount}
        actions={rowActions?.(check)}
      />
    ));

  return (
    <Box
      component="section"
      sx={{ borderTop: 1, borderColor: 'divider', pt: 0.5 }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          minHeight: theme => theme.spacing(3.5),
        }}
      >
        <Box
          component="button"
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(o => !o)}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            p: 0,
            border: 0,
            bgcolor: 'transparent',
            font: 'inherit',
            cursor: 'pointer',
            minWidth: 0,
          }}
        >
          <ChevronRightIcon
            sx={{
              fontSize: theme => theme.spacing(2),
              color: 'text.secondary',
              transform: open ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.15s',
            }}
          />
          <Tooltip title={titleHint ?? ''} disableHoverListener={!titleHint}>
            <Typography
              variant="body2"
              component="h3"
              noWrap
              sx={{ fontWeight: 600, color: 'text.primary' }}
            >
              {title}
            </Typography>
          </Tooltip>
        </Box>
        {total > 0 && (
          <Typography variant="caption" color="text.secondary">
            {`${passed} of ${total} passed`}
          </Typography>
        )}
        <Box sx={{ flex: 1 }} />
        {headerActions}
      </Box>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <Box sx={{ pb: 0.5, pl: 2.5 }}>
          {intro && (
            <Box>
              <Box
                component="button"
                type="button"
                aria-expanded={showIntro}
                onClick={() => setShowIntro(v => !v)}
                sx={{
                  p: 0,
                  border: 0,
                  bgcolor: 'transparent',
                  font: 'inherit',
                  cursor: 'pointer',
                  color: 'primary.main',
                  typography: 'caption',
                }}
              >
                {showIntro
                  ? 'Hide goal and restrictions'
                  : 'Show goal and restrictions'}
              </Box>
              <Collapse in={showIntro} timeout="auto" unmountOnExit>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                    mt: 0.5,
                    mb: 0.5,
                  }}
                >
                  {intro}
                </Box>
              </Collapse>
            </Box>
          )}
          {hasKinds ? (
            <>
              {mustDo.length > 0 && (
                <Typography
                  variant="caption"
                  component="h4"
                  sx={theme => ({
                    ...overlineSx(theme),
                    display: 'block',
                    mt: 0.5,
                  })}
                >
                  Must do
                </Typography>
              )}
              {rows(mustDo)}
              {mustNotDo.length > 0 && (
                <Typography
                  variant="caption"
                  component="h4"
                  sx={theme => ({
                    ...overlineSx(theme),
                    display: 'block',
                    mt: 0.5,
                  })}
                >
                  Must not do
                </Typography>
              )}
              {rows(mustNotDo)}
            </>
          ) : (
            rows(checks)
          )}
          {footer}
        </Box>
      </Collapse>
    </Box>
  );
}
