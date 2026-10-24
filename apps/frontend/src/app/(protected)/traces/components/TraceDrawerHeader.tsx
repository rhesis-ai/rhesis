'use client';

import { Fragment } from 'react';
import Link from 'next/link';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import { CloseIcon } from '@/components/icons';
import { GridBadge } from '@/components/common/GridBadge';
import { useCurrency } from '@/contexts/CurrencyContext';
import type { TraceDetailResponse } from '@/utils/api-client/interfaces/telemetry';
import { formatDuration } from '@/utils/format-duration';
import { formatTokenCount, tokenSplitLabel } from '@/utils/trace-utils';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import { experimentHref } from '@/utils/experiment-links';
import TurnSwitcher from './TurnSwitcher';

export interface TraceExperimentInfo {
  id: string;
  name: string;
  version: string;
}

interface TraceDrawerHeaderProps {
  trace: TraceDetailResponse;
  experiment: TraceExperimentInfo | null;
  turnIndex: number | null;
  turnCount: number;
  onTurnChange: (index: number) => void;
  onClose: () => void;
}

interface ContextLink {
  key: string;
  label?: string;
  href: string;
  text: string;
  mono?: boolean;
}

function contextLinks(
  trace: TraceDetailResponse,
  experiment: TraceExperimentInfo | null
): ContextLink[] {
  const links: ContextLink[] = [];
  if (trace.project) {
    links.push({
      key: 'project',
      href: `/projects/${trace.project.id}`,
      text: trace.project.name,
    });
  }
  if (trace.endpoint) {
    links.push({
      key: 'endpoint',
      href: `/endpoints/${trace.endpoint.id}`,
      text: trace.endpoint.name,
    });
  }
  if (trace.test_run) {
    links.push({
      key: 'run',
      label: 'Run',
      href: `/test-runs/${trace.test_run.id}`,
      text: trace.test_run.name || trace.test_run.nano_id || trace.test_run.id,
    });
  }
  if (trace.test) {
    links.push({
      key: 'test',
      label: 'Test',
      href: `/tests/${trace.test.id}`,
      text: trace.test.nano_id || trace.test.id,
      mono: true,
    });
  }
  if (experiment) {
    links.push({
      key: 'experiment',
      label: 'Experiment',
      href: experimentHref(experiment.id, experiment.version),
      text: experiment.version
        ? `${experiment.name} (${shortVersion(experiment.version)})`
        : experiment.name,
    });
  }
  return links;
}

const dotSx = { color: 'text.disabled' } as const;

/**
 * One bar for the whole trace: what it is, where it ran, its totals, the turn
 * switcher and the close button. Replaces the label/pill rows and the footer.
 */
export default function TraceDrawerHeader({
  trace,
  experiment,
  turnIndex,
  turnCount,
  onTurnChange,
  onClose,
}: TraceDrawerHeaderProps) {
  const { format: money } = useCurrency();
  const links = contextLinks(trace, experiment);
  const title = trace.root_spans[0]?.span_name;

  const stats: { key: string; text: string; title?: string }[] = [
    { key: 'spans', text: `${trace.span_count} spans` },
    { key: 'duration', text: formatDuration(trace.duration_ms) },
  ];
  if (trace.total_tokens > 0) {
    stats.push({
      key: 'tokens',
      text: `${formatTokenCount(trace.total_tokens)} tok`,
      title: tokenSplitLabel(
        trace.total_input_tokens,
        trace.total_output_tokens
      ),
    });
  }
  // Zero is a figure somebody computed; only a trace with no cost at all goes without.
  if (typeof trace.total_cost_usd === 'number') {
    stats.push({ key: 'cost', text: money(trace.total_cost_usd) });
  }

  return (
    <Box
      component="header"
      sx={{
        flexShrink: 0,
        minHeight: theme => theme.spacing(6.5),
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        pl: 2.5,
        pr: 1.5,
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          minWidth: 0,
          flex: 1,
        }}
      >
        {title && (
          <Typography
            variant="body2"
            component="h2"
            sx={theme => ({
              fontFamily: theme.typography.fontFamilyCode,
              fontWeight: 600,
              color: 'text.primary',
              whiteSpace: 'nowrap',
            })}
          >
            {title}
          </Typography>
        )}
        <Box
          component="nav"
          aria-label="Trace context"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            minWidth: 0,
            overflow: 'hidden',
            whiteSpace: 'nowrap',
          }}
        >
          {links.map((link, i) => (
            <Fragment key={link.key}>
              {i > 0 && (
                <Typography variant="caption" aria-hidden sx={dotSx}>
                  {link.key === 'endpoint' && links[i - 1].key === 'project'
                    ? '›'
                    : '·'}
                </Typography>
              )}
              {link.label && (
                <Typography variant="caption" color="text.secondary">
                  {link.label}
                </Typography>
              )}
              <Typography
                variant="caption"
                component={Link}
                href={link.href}
                target="_blank"
                sx={theme => ({
                  color: 'primary.main',
                  textDecoration: 'none',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  ...(link.mono
                    ? { fontFamily: theme.typography.fontFamilyCode }
                    : {}),
                  '&:hover': { textDecoration: 'underline' },
                })}
              >
                {link.text}
              </Typography>
            </Fragment>
          ))}
        </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
      >
        {stats.map((stat, i) => (
          <Fragment key={stat.key}>
            {i > 0 && (
              <Typography variant="caption" aria-hidden sx={dotSx}>
                ·
              </Typography>
            )}
            <Tooltip
              title={stat.title ?? ''}
              disableHoverListener={!stat.title}
            >
              <Typography variant="caption" color="text.secondary">
                {stat.text}
              </Typography>
            </Tooltip>
          </Fragment>
        ))}
        {trace.environment && (
          <GridBadge label={trace.environment} size="grid" />
        )}
        {trace.error_count > 0 && (
          <GridBadge
            label={`${trace.error_count} errors`}
            size="grid"
            sx={{ bgcolor: 'error.main', color: 'error.contrastText' }}
          />
        )}
      </Box>

      {turnCount > 1 && (
        <Box
          sx={{
            flexShrink: 0,
            pl: 1.5,
            borderLeft: 1,
            borderColor: 'divider',
          }}
        >
          <TurnSwitcher
            index={turnIndex}
            count={turnCount}
            onChange={onTurnChange}
          />
        </Box>
      )}

      <Tooltip title="Close (Esc)">
        <IconButton size="small" aria-label="Close trace" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
