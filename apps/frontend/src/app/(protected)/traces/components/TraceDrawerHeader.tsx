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
  /** Omitted when embedded, where there is nothing to close. */
  onClose?: () => void;
}

/** Header width (px) below which an item is dropped; lowest priority goes first. */
const HIDE_BELOW = {
  experiment: 1500,
  spans: 1350,
  endpoint: 1200,
  environment: 1050,
  tokens: 950,
  run: 800,
} as const;

/** Hides an element once the header is narrower than `px`. */
function hideBelow(px?: number) {
  return px
    ? { [`@container (max-width: ${px - 1}px)`]: { display: 'none' } }
    : {};
}

/** An item's leading dot shows only while some item before it does. */
function separatorHideBelow(items: { hideBelow?: number }[], i: number) {
  return Math.min(...items.slice(0, i).map(item => item.hideBelow ?? 0));
}

interface ContextLink {
  key: string;
  label?: string;
  href: string;
  text: string;
  mono?: boolean;
  hideBelow?: number;
}

function contextLinks(
  trace: TraceDetailResponse,
  experiment: TraceExperimentInfo | null
): ContextLink[] {
  // No project link: traces are always viewed inside the active project.
  const links: ContextLink[] = [];
  if (trace.endpoint) {
    links.push({
      key: 'endpoint',
      href: `/endpoints/${trace.endpoint.id}`,
      text: trace.endpoint.name,
      hideBelow: HIDE_BELOW.endpoint,
    });
  }
  if (trace.test_run) {
    links.push({
      key: 'run',
      label: 'Run',
      href: `/test-runs/${trace.test_run.id}`,
      text: trace.test_run.name || trace.test_run.nano_id || trace.test_run.id,
      hideBelow: HIDE_BELOW.run,
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
      hideBelow: HIDE_BELOW.experiment,
    });
  }
  return links;
}

const dotSx = { color: 'text.disabled' } as const;

/**
 * One bar for the whole trace: what it is, where it ran, its totals, the turn
 * switcher and the close button. Replaces the label/pill rows and the footer.
 * As the bar narrows, whole items drop out by priority instead of truncating.
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

  const stats: {
    key: string;
    text: string;
    title?: string;
    hideBelow?: number;
  }[] = [
    {
      key: 'spans',
      text: `${trace.span_count} spans`,
      hideBelow: HIDE_BELOW.spans,
    },
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
      hideBelow: HIDE_BELOW.tokens,
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
        containerType: 'inline-size',
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
                <Typography
                  variant="caption"
                  aria-hidden
                  sx={{ ...dotSx, ...hideBelow(separatorHideBelow(links, i)) }}
                >
                  ·
                </Typography>
              )}
              {link.label && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={hideBelow(link.hideBelow)}
                >
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
                  ...hideBelow(link.hideBelow),
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
              <Typography
                variant="caption"
                aria-hidden
                sx={{ ...dotSx, ...hideBelow(separatorHideBelow(stats, i)) }}
              >
                ·
              </Typography>
            )}
            <Tooltip
              title={stat.title ?? ''}
              disableHoverListener={!stat.title}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={hideBelow(stat.hideBelow)}
              >
                {stat.text}
              </Typography>
            </Tooltip>
          </Fragment>
        ))}
        {trace.environment && (
          <GridBadge
            label={trace.environment}
            size="grid"
            sx={hideBelow(HIDE_BELOW.environment)}
          />
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

      {onClose && (
        <Tooltip title="Close (Esc)">
          <IconButton size="small" aria-label="Close trace" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
}
