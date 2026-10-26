'use client';

import { Fragment } from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { format } from 'date-fns';
import { GridBadge } from '@/components/common/GridBadge';
import { useCurrency } from '@/contexts/CurrencyContext';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { formatDuration } from '@/utils/format-duration';
import { formatTokenCount, subtreeUsage } from '@/utils/trace-utils';
import { getSpanColor, getSpanIcon } from '@/utils/span-icon-mapper';
import CopyButton from './CopyButton';

interface SpanHeaderProps {
  span: SpanNode;
  traceId?: string;
}

const monoSx = (theme: Theme) => ({
  fontFamily: theme.typography.fontFamilyCode,
});

function shortId(id: string): string {
  return id.length > 20 ? `${id.slice(0, 8)}…${id.slice(-8)}` : id;
}

function clockTime(value: string): string {
  try {
    return format(new Date(value), 'HH:mm:ss.SSS');
  } catch {
    return value;
  }
}

const Dot = () => (
  <Typography variant="caption" aria-hidden sx={{ color: 'text.disabled' }}>
    ·
  </Typography>
);

/**
 * Who the span is and what it cost, in two lines: name, type and totals, then
 * the IDs and timing that are only needed now and then.
 */
export default function SpanHeader({ span, traceId }: SpanHeaderProps) {
  const { format: money } = useCurrency();
  const SpanIcon = getSpanIcon(span);
  const color = getSpanColor(span, span.status_code);
  // Rolled up over the subtree: only ai.llm.invoke leaves carry token attributes.
  const usage = subtreeUsage(span);
  const isError = span.status_code === 'ERROR';

  const totals: { key: string; text: string; title?: string }[] = [
    {
      key: 'duration',
      text: formatDuration(span.duration_ms),
      title: `${format(new Date(span.start_time), 'PPpp')} → ${format(new Date(span.end_time), 'PPpp')}`,
    },
  ];
  if (usage) {
    const split =
      usage.input > 0 || usage.output > 0
        ? `${formatTokenCount(usage.input)} input · ${formatTokenCount(usage.output)} output`
        : '';
    const rolled =
      usage.llmSpanCount > 0
        ? `rolled up from ${usage.llmSpanCount} LLM ${usage.llmSpanCount === 1 ? 'span' : 'spans'}`
        : '';
    totals.push({
      key: 'tokens',
      text: `${formatTokenCount(usage.total)} tok`,
      title: [split, rolled].filter(Boolean).join(' · '),
    });
    if (usage.costUsd !== null) {
      totals.push({ key: 'cost', text: money(usage.costUsd) });
    }
  }

  return (
    <Box
      sx={{
        flexShrink: 0,
        px: 2,
        py: 1.25,
        borderBottom: 1,
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
        <Box
          component={SpanIcon}
          aria-hidden
          sx={{ fontSize: theme => theme.spacing(2.25), color, flexShrink: 0 }}
        />
        <Typography
          variant="body2"
          component="h2"
          noWrap
          title={span.span_name}
          sx={theme => ({ ...monoSx(theme), fontWeight: 600, minWidth: 0 })}
        >
          {span.span_name}
        </Typography>
        {span.model_name && (
          <GridBadge
            label={span.model_name}
            size="grid"
            sx={theme => monoSx(theme)}
          />
        )}
        {isError && (
          <GridBadge
            label="ERROR"
            size="grid"
            sx={{ bgcolor: 'error.main', color: 'error.contrastText' }}
          />
        )}
        <Box sx={{ flex: 1 }} />
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          {totals.map((total, i) => (
            <Fragment key={total.key}>
              {i > 0 && <Dot />}
              <Tooltip
                title={total.title ?? ''}
                disableHoverListener={!total.title}
              >
                <Typography
                  variant="caption"
                  color={i === 0 ? 'text.primary' : 'text.secondary'}
                  sx={i === 0 ? { fontWeight: 600 } : undefined}
                >
                  {total.text}
                </Typography>
              </Tooltip>
            </Fragment>
          ))}
        </Box>
      </Box>

      {isError && span.status_message && (
        <Typography variant="caption" color="error.main">
          {span.status_message}
        </Typography>
      )}

      <Box
        sx={theme => ({
          ...monoSx(theme),
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          columnGap: 0.75,
          color: 'text.secondary',
          typography: 'caption',
        })}
      >
        <Box
          component="span"
          sx={{ display: 'inline-flex', alignItems: 'center' }}
        >
          span {span.span_id}
          <CopyButton text={span.span_id} label="Copy span ID" />
        </Box>
        {traceId && (
          <>
            <Dot />
            <Box
              component="span"
              title={traceId}
              sx={{ display: 'inline-flex', alignItems: 'center' }}
            >
              trace {shortId(traceId)}
              <CopyButton text={traceId} label="Copy trace ID" />
            </Box>
          </>
        )}
        <Dot />
        <span>
          {clockTime(span.start_time)} → {clockTime(span.end_time)}
        </span>
        <Dot />
        <span>{span.span_kind}</span>
      </Box>
    </Box>
  );
}
