'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  LinearProgress,
  Paper,
  Typography,
} from '@mui/material';

import { Can, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { PageLayout } from '@/components/layout/PageLayout';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useNotifications } from '@/components/common/NotificationContext';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { jobKeys } from '@/constants/query-keys';
import type { Job } from '@/utils/api-client/interfaces/job';
import { JOB_STATUS_COLOR, JOB_STATUS_LABEL } from '@/constants/jobs';
import { BORDER_RADIUS } from '@/styles/theme';
import ActivityLogViewer from './components/ActivityLogViewer';

/**
 * How often to re-read a job that is still running.
 *
 * Polling rather than the WebSocket for now: the events layer that would push
 * `job.*` updates is not built yet, and a fixed interval on an open detail view
 * is cheap. The interval stops as soon as the job reports itself terminal, so an
 * idle tab costs nothing.
 */
const LIVE_POLL_MS = 3000;

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2">{value}</Typography>
    </Box>
  );
}

function formatTimestamp(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export default function JobDetailPage() {
  const params = useParams();
  const { status: sessionStatus } = useSession();
  const queryClient = useQueryClient();
  const notifications = useNotifications();

  const jobId = typeof params.identifier === 'string' ? params.identifier : '';

  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Job.READ
  );

  const [follow, setFollow] = React.useState(true);
  const [cancelling, setCancelling] = React.useState(false);

  const enabled = isAuthenticated(sessionStatus) && canRead && jobId !== '';

  const { data: job, error: jobError } = useQuery<Job>({
    queryKey: jobKeys.detail(jobId),
    enabled,
    queryFn: () => new ApiClientFactory().getJobsClient().getJob(jobId),
    // Stop polling once the backend says the job has stopped. is_terminal is
    // served rather than derived here so this does not need its own list of
    // which statuses are final.
    refetchInterval: query =>
      query.state.data?.is_terminal ? false : LIVE_POLL_MS,
  });

  const { data: activity } = useQuery({
    queryKey: jobKeys.activity(jobId),
    enabled,
    queryFn: () => new ApiClientFactory().getJobsClient().getJobActivity(jobId),
    refetchInterval: job?.is_terminal ? false : LIVE_POLL_MS,
  });

  useDocumentTitle(job?.name ? `Job: ${job.name}` : 'Job');

  // Memoized so the copy callback below is not rebuilt on every render.
  const entries = React.useMemo(() => activity?.entries ?? [], [activity]);

  const handleCopy = React.useCallback(() => {
    const text = entries
      .map(
        e => `${new Date(e.created_at).toISOString()} [${e.level}] ${e.message}`
      )
      .join('\n');
    navigator.clipboard.writeText(text).then(
      () => notifications.show('Activity copied', { severity: 'success' }),
      () => notifications.show('Could not copy activity', { severity: 'error' })
    );
  }, [entries, notifications]);

  const handleCancel = React.useCallback(async () => {
    setCancelling(true);
    try {
      await new ApiClientFactory().getJobsClient().cancelJob(jobId);
      // "Requested", not "cancelled": the job stops when it notices, so saying
      // it has stopped would be a lie.
      notifications.show('Cancellation requested', { severity: 'info' });
      queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) });
    } catch {
      notifications.show('Could not cancel this job', { severity: 'error' });
    } finally {
      setCancelling(false);
    }
  }, [jobId, notifications, queryClient]);

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="jobs" />;

  if (jobError) {
    return (
      <PageLayout
        title="Job"
        breadcrumbs={[{ label: 'Jobs', href: '/jobs' }, { label: 'Not found' }]}
      >
        <Alert severity="error">
          This job could not be loaded. It may have been removed by the
          retention sweep, or belong to another project.
        </Alert>
      </PageLayout>
    );
  }

  if (!job) return <PageLoadingState />;

  const jobStatus = job.status as keyof typeof JOB_STATUS_COLOR;
  const showProgress =
    job.progress_current !== undefined &&
    job.progress_current !== null &&
    !!job.progress_total;

  return (
    <PageLayout
      title={job.name || job.job_type}
      breadcrumbs={[
        { label: 'Jobs', href: '/jobs' },
        { label: job.name || job.job_type },
      ]}
      actions={
        job.cancellable ? (
          <Can capability={Capability.Job.CANCEL}>
            <Button
              variant="outlined"
              color="warning"
              onClick={handleCancel}
              disabled={cancelling}
            >
              {cancelling ? 'Requesting…' : 'Cancel job'}
            </Button>
          </Can>
        ) : undefined
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: BORDER_RADIUS.md }}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field
                label="Status"
                value={
                  <Chip
                    size="small"
                    label={JOB_STATUS_LABEL[jobStatus] ?? job.status}
                    color={JOB_STATUS_COLOR[jobStatus] ?? 'default'}
                  />
                }
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field label="Type" value={job.job_type} />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field label="Queued" value={formatTimestamp(job.queued_at)} />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field label="Started" value={formatTimestamp(job.started_at)} />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field
                label="Finished"
                value={formatTimestamp(job.finished_at)}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Field
                label="Attempt"
                value={job.attempt > 0 ? job.attempt + 1 : 1}
              />
            </Grid>
            {job.entity_type && job.entity_id && (
              <Grid size={{ xs: 6, sm: 3 }}>
                <Field
                  label="Subject"
                  value={`${job.entity_type} ${job.entity_id.slice(0, 8)}`}
                />
              </Grid>
            )}
          </Grid>

          {showProgress && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {job.progress_current} / {job.progress_total}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(
                  100,
                  Math.round(
                    ((job.progress_current ?? 0) / (job.progress_total ?? 1)) *
                      100
                  )
                )}
              />
            </Box>
          )}

          {job.status === 'cancelling' && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Cancellation requested. The job stops at its next checkpoint, so
              work already in flight may still finish.
            </Alert>
          )}

          {job.error_message && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {job.error_type ? `${job.error_type}: ` : ''}
              {job.error_message}
            </Alert>
          )}
        </Paper>

        <ActivityLogViewer
          entries={entries}
          live={!job.is_terminal}
          follow={follow}
          onFollowChange={setFollow}
          onCopy={handleCopy}
        />

        {job.is_terminal && entries.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            This job finished without recording any activity. Older jobs lose
            their log entries before the job row itself is removed.
          </Typography>
        )}
      </Box>
    </PageLayout>
  );
}
