import type { ReactNode } from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import type { TooltipProps } from '@mui/material/Tooltip';
import type { AdaptiveMetricEvalDetail } from '@/utils/api-client/interfaces/adaptive-testing';

function resolveMetricReason(m: AdaptiveMetricEvalDetail): string | null {
  if (typeof m.reason === 'string' && m.reason.trim()) {
    return m.reason.trim();
  }
  const d = m.details;
  if (d && typeof d.reason === 'string' && d.reason.trim()) {
    return d.reason.trim();
  }
  return null;
}

/**
 * Score chip tooltip: opaque surface (avoids bleed-through on DataGrid) and title content
 * that shows only Name / Reason per metric (not score or pass/fail, which the chip/label show).
 */
export function ScoreMetricsTooltip({
  metrics,
  children,
}: {
  metrics: Record<string, AdaptiveMetricEvalDetail> | null | undefined;
  children: TooltipProps['children'];
}) {
  return (
    <Tooltip
      title={renderScoreMetricsTooltip(metrics)}
      arrow
      placement="top"
      enterDelay={200}
      slotProps={{
        tooltip: {
          sx: theme => {
            const bg =
              theme.palette.mode === 'dark'
                ? theme.palette.grey[900]
                : theme.palette.grey[50];
            return {
              bgcolor: bg,
              color: theme.palette.text.primary,
              border: `1px solid ${theme.palette.divider}`,
              boxShadow: theme.shadows[12],
              opacity: 1,
              maxWidth: 440,
              p: 1.5,
              backdropFilter: 'none',
            };
          },
        },
        arrow: {
          sx: theme => ({
            color:
              theme.palette.mode === 'dark'
                ? theme.palette.grey[900]
                : theme.palette.grey[50],
          }),
        },
        popper: {
          sx: {
            zIndex: theme => theme.zIndex.modal + 2,
          },
        },
      }}
    >
      {children}
    </Tooltip>
  );
}

/** Tooltip title: Name / Reason lines for each metric. */
export function renderScoreMetricsTooltip(
  metrics: Record<string, AdaptiveMetricEvalDetail> | null | undefined
): ReactNode {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <Typography variant="body2" component="span">
        Aggregate score (no per-metric breakdown).
      </Typography>
    );
  }

  return (
    <Box sx={{ maxWidth: 420, maxHeight: 280, overflow: 'auto' }}>
      {Object.entries(metrics).map(([name, m]) => {
        const reason = resolveMetricReason(m);
        return (
          <Box key={name} sx={{ mb: 1 }}>
            <Typography
              variant="caption"
              display="block"
              sx={{ whiteSpace: 'pre-wrap' }}
            >
              <Box component="span" fontWeight={600}>
                Name:{' '}
              </Box>
              {name}
            </Typography>
            <Typography
              variant="caption"
              display="block"
              color="text.secondary"
              sx={{ mt: 0.25, whiteSpace: 'pre-wrap' }}
            >
              <Box component="span" fontWeight={600} color="text.primary">
                Reason:{' '}
              </Box>
              {reason ?? '—'}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}
