'use client';

import * as React from 'react';
import Link from 'next/link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import DownloadIcon from '@mui/icons-material/Download';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { SectionCard } from '@/components/common/SectionCard';
import { JOB_STATUS_COLOR, JOB_STATUS_LABEL } from '@/constants/jobs';
import type { Job, JobStatus } from '@/utils/api-client/interfaces/job';
import { getApiErrorMessage } from '@/utils/error-utils';
import { AuditLogClient } from '../api/audit-log-client';
import {
  RECENT_EXPORTS_LIMIT,
  useAuditExports,
} from '../hooks/useAuditExports';
import { jobUrl } from '../labels';
import { monoSx } from './AuditChanges';
import AuditExportDialog from './AuditExportDialog';

const COMPLETED: JobStatus = 'completed';
const FAILED: JobStatus = 'failed';

function metadataString(job: Job, key: string): string | undefined {
  const value = job.job_metadata?.[key];
  return typeof value === 'string' && value ? value : undefined;
}

function StatusCell({ job }: { job: Job }) {
  const status = job.status as JobStatus;
  const { progress_current: current, progress_total: total } = job;
  const label =
    !job.is_terminal && total
      ? `${JOB_STATUS_LABEL[status] ?? job.status} ${Math.round(((current ?? 0) / total) * 100)}%`
      : (JOB_STATUS_LABEL[status] ?? job.status);
  const chip = (
    <Chip
      size="small"
      label={label}
      color={JOB_STATUS_COLOR[status] ?? 'default'}
    />
  );
  if (job.status === FAILED && job.error_message) {
    return <Tooltip title={job.error_message}>{chip}</Tooltip>;
  }
  return chip;
}

/** The signed-in user's recent exports, each downloadable once its job completes. */
export default function AuditExportsSection() {
  const { data: jobs, isLoading, error } = useAuditExports();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const client = React.useMemo(() => new AuditLogClient(), []);

  let body: React.ReactNode;
  if (isLoading) {
    body = (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  } else if (error) {
    body = (
      <Alert severity="error">
        {getApiErrorMessage(error, 'Could not load your exports.')}
      </Alert>
    );
  } else if (!jobs || jobs.length === 0) {
    body = (
      <EntityEmptyState
        icon={FileDownloadOutlinedIcon}
        title="No exports yet"
        description="Export the whole log here, or the events you have filtered with Export on the Events list."
      />
    );
  } else {
    body = (
      <Table size="small" aria-label="Your exports">
        <TableHead>
          <TableRow>
            <TableCell>Started</TableCell>
            <TableCell>Format</TableCell>
            <TableCell>Events</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {jobs.map(job => {
            const filter = metadataString(job, 'filter');
            const format = metadataString(job, 'format');
            const done = job.status === COMPLETED;
            return (
              <TableRow key={job.id}>
                <TableCell>
                  {new Date(job.created_at).toLocaleString()}
                </TableCell>
                <TableCell>{format?.toUpperCase() ?? '—'}</TableCell>
                <TableCell>
                  {filter ? (
                    <Tooltip title={<Box sx={monoSx}>{filter}</Box>}>
                      <span>Filtered</span>
                    </Tooltip>
                  ) : (
                    'All events'
                  )}
                </TableCell>
                <TableCell>
                  <StatusCell job={job} />
                </TableCell>
                <TableCell align="right">
                  <Box
                    sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}
                  >
                    <Button size="small" component={Link} href={jobUrl(job.id)}>
                      View job
                    </Button>
                    {done ? (
                      // A plain link: the browser follows the redirect to
                      // storage, or saves the streamed file.
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        href={client.exportDownloadUrl(job.id)}
                        download
                      >
                        Download
                      </Button>
                    ) : (
                      // No link before the job completes: the backend answers 409.
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        disabled
                      >
                        Download
                      </Button>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  }

  return (
    <>
      <SectionCard
        title="Exports"
        subtitle={`Your last ${RECENT_EXPORTS_LIMIT} exports. Each download is recorded in the log.`}
        actions={
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={() => setDialogOpen(true)}
          >
            Export all events
          </Button>
        }
      >
        {body}
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 2 }}
        >
          Exports never include content values, even when the log keeps them.
        </Typography>
      </SectionCard>
      <AuditExportDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </>
  );
}
