'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import { useAnnounce } from '@/components/common/LiveAnnouncer';
import { getApiErrorMessage } from '@/utils/error-utils';
import type {
  MetricTargetPreview,
  MetricTargetPreviewSample,
} from '@/utils/api-client/interfaces/metric';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import TargetSummaryText from './TargetSummaryText';

/** The span status the preview reports for a failed span: the SDK's `SpanStatus`. */
const ERROR_STATUS = 'error';

interface TargetPreviewPanelProps {
  preview: MetricTargetPreview | undefined;
  /** The draft changed and the preview hasn't caught up yet. */
  stale: boolean;
  loading: boolean;
  error: Error | null;
  /** Why there is nothing to preview yet (an incomplete draft), or null. */
  blocked: string | null;
  /** No project to read traces from. */
  noProject: boolean;
  /** How many latest traces the preview reads. */
  traces: number;
  /** "spans", "turns": what one unit of the target is called. */
  unitNoun: { one: string; many: string };
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function formatDuration(ms: number | null | undefined): string | null {
  if (ms === null || ms === undefined) return null;
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

/** What screen readers hear when the counts change. */
export function previewAnnouncement(
  preview: MetricTargetPreview,
  unitNoun: { one: string; many: string }
): string {
  if (preview.traces === 0) return 'Preview: no traces yet.';
  if (preview.matching_traces === 0) {
    return `Preview: nothing matches in the last ${plural(preview.traces, 'trace', 'traces')}.`;
  }
  return `Preview: ${plural(preview.units, unitNoun.one, unitNoun.many)} in ${plural(
    preview.matching_traces,
    'trace',
    'traces'
  )}; ${plural(preview.not_applicable_traces, 'trace', 'traces')} not applicable.`;
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <Box
      sx={{
        flex: 1,
        p: 1.5,
        bgcolor: 'action.hover',
        borderRadius: BORDER_RADIUS.sm,
      }}
    >
      <Typography variant="h5" component="p">
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

function SampleText({ label, text }: { label: string; text?: string | null }) {
  if (!text) return null;
  return (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="caption"
        component="span"
        sx={{
          fontFamily: theme => theme.typography.fontFamilyCode,
          overflow: 'hidden',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          wordBreak: 'break-word',
        }}
      >
        {text}
      </Typography>
    </Box>
  );
}

function Sample({ sample }: { sample: MetricTargetPreviewSample }) {
  const failed = sample.status === ERROR_STATUS;
  const duration = formatDuration(sample.duration_ms);
  return (
    <Box
      component="li"
      sx={{
        p: 1.5,
        border: 1,
        borderColor: 'divider',
        borderRadius: BORDER_RADIUS.sm,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
        <Typography
          variant="body2"
          sx={{
            fontFamily: theme => theme.typography.fontFamilyCode,
            fontWeight: 'medium',
            wordBreak: 'break-all',
          }}
        >
          {sample.name ?? sample.span_id ?? sample.trace_id}
        </Typography>
        {duration && (
          <Typography variant="caption" color="text.secondary">
            {duration}
          </Typography>
        )}
      </Box>
      {failed && (
        <Typography variant="caption" color="error.main">
          Status: error
        </Typography>
      )}
      <SampleText label="in" text={sample.input} />
      <SampleText label="out" text={sample.output} />
    </Box>
  );
}

/**
 * What the draft target picks in the latest traces: how many units in how many
 * traces, how many traces it doesn't apply to, and a few of the units. Says
 * what the endpoint must report when nothing matches.
 */
export default function TargetPreviewPanel({
  preview,
  stale,
  loading,
  error,
  blocked,
  noProject,
  traces,
  unitNoun,
}: TargetPreviewPanelProps) {
  const headingId = React.useId();
  const announce = useAnnounce();
  const announced = React.useRef<string | null>(null);

  // Polite, and once per settled result, so typing doesn't flood the reader. An
  // edit clears the last message: the same counts after an edit are news too.
  React.useEffect(() => {
    if (stale) {
      announced.current = null;
      return;
    }
    if (!preview || loading) return;
    const message = previewAnnouncement(preview, unitNoun);
    if (message === announced.current) return;
    announced.current = message;
    announce(message);
  }, [preview, stale, loading, unitNoun, announce]);

  const body = () => {
    if (noProject) {
      return (
        <Typography variant="body2" color="text.secondary">
          No project is selected, so there are no traces to preview.
        </Typography>
      );
    }
    if (blocked) {
      return (
        <Typography variant="body2" color="text.secondary">
          {blocked}
        </Typography>
      );
    }
    if (error) {
      return (
        <Alert severity="error" data-testid="target-preview-error">
          {getApiErrorMessage(error, 'The preview failed.')}
        </Alert>
      );
    }
    if (!preview) {
      return (
        <Box aria-hidden>
          <Skeleton
            variant="rounded"
            sx={{ height: theme => theme.spacing(8) }}
          />
          <Skeleton variant="text" sx={{ mt: 1 }} />
        </Box>
      );
    }
    if (preview.traces === 0) {
      return (
        <Box data-testid="target-preview-no-traces">
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            No traces yet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Send traces from the endpoint, and this shows what the target picks
            in them.
          </Typography>
        </Box>
      );
    }
    if (preview.matching_traces === 0) {
      return (
        <Box data-testid="target-preview-no-match">
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            Nothing matches in the last{' '}
            {plural(preview.traces, 'trace', 'traces')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Every one would be not applicable.
            {preview.target_summary ? (
              <>
                {' '}
                For this metric to run, the endpoint must report{' '}
                <TargetSummaryText summary={preview.target_summary} /> in its
                traces. Check the field names against a trace, or send traces
                that carry them.
              </>
            ) : (
              ' Check the field names against a trace, or send traces that carry them.'
            )}
          </Typography>
        </Box>
      );
    }
    return (
      <>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Stat
            value={preview.units}
            label={`${preview.units === 1 ? unitNoun.one : unitNoun.many} in ${plural(
              preview.matching_traces,
              'trace',
              'traces'
            )}`}
          />
          <Stat
            value={preview.not_applicable_traces}
            label={`${preview.not_applicable_traces === 1 ? 'trace' : 'traces'} not applicable`}
          />
        </Box>
        {preview.samples.length > 0 && (
          <Box
            component="ul"
            aria-label="Examples"
            sx={{
              listStyle: 'none',
              p: 0,
              m: 0,
              mt: 2,
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
            }}
          >
            {preview.samples.map(sample => (
              <Sample
                key={`${sample.trace_id}:${sample.span_id ?? ''}`}
                sample={sample}
              />
            ))}
          </Box>
        )}
      </>
    );
  };

  return (
    <Paper
      variant="outlined"
      component="section"
      aria-labelledby={headingId}
      aria-busy={loading || stale}
      data-testid="target-preview"
      sx={{
        p: 2,
        borderRadius: BORDER_RADIUS.md,
        opacity: stale && preview ? 0.6 : 1,
        transition: theme => theme.transitions.create('opacity'),
      }}
    >
      <Typography id={headingId} variant="subtitle1" component="h3">
        Matches in recent traces
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        The last {plural(traces, 'trace', 'traces')} of this project
      </Typography>
      {body()}
    </Paper>
  );
}
