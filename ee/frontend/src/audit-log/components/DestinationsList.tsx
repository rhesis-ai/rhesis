'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import {
  Delete as DeleteIcon,
  Link as WebhookIcon,
  Pause as PauseIcon,
  PlayArrow as ResumeIcon,
  Send as SendIcon,
} from '@mui/icons-material';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import {
  DestinationKind,
  DestinationStatus,
  destinationStatus,
  destinationTarget,
  kindLabel,
  type AuditDestination,
} from '../destinations';
import { listRowSx, listSx } from './AuditApiAccessCard';
import { monoSx } from './AuditChanges';
import { StatusPill, type Tone } from './tones';

export interface DestinationsListProps {
  destinations: AuditDestination[];
  /** Ids with a test event in flight. */
  testing: ReadonlySet<string>;
  onTest: (destination: AuditDestination) => void;
  onSetPaused: (destination: AuditDestination, paused: boolean) => void;
  onDelete: (destination: AuditDestination) => Promise<void>;
}

const STATUS_CHIPS: Record<
  DestinationStatus,
  { label: string; tone: Tone | 'default'; hint: string }
> = {
  active: {
    label: 'Active',
    tone: 'success',
    hint: 'New events are sent within seconds.',
  },
  paused: {
    label: 'Paused',
    tone: 'default',
    hint: 'Nothing is sent. Resume to continue from the last delivered event.',
  },
  auto_paused: {
    label: 'Auto-paused',
    tone: 'error',
    hint:
      'Paused itself after failing for about 13 hours. Fix the receiver, ' +
      'then resume to continue from the last delivered event.',
  },
};

/** Short marks for the kind tile; webhooks get an icon. */
const KIND_MARKS: Record<string, string> = {
  [DestinationKind.SPLUNK_HEC]: 'SPL',
  [DestinationKind.DATADOG]: 'DD',
};

const tileSx = {
  width: AVATAR_SIZES.MEDIUM,
  height: AVATAR_SIZES.MEDIUM,
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: BORDER_RADIUS.sm,
  bgcolor: (t: Theme) => t.palette.greyscale.surface2,
  color: 'text.secondary',
  typography: 'captionBold',
} as const;

function KindTile({ kind }: { kind: string }) {
  const mark = KIND_MARKS[kind];
  return (
    <Box sx={tileSx} aria-hidden>
      {mark ?? <WebhookIcon fontSize="small" />}
    </Box>
  );
}

function formatTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '';
}

function Health({ destination: d }: { destination: AuditDestination }) {
  const lastSuccess = d.last_success_at
    ? `Last delivered ${formatTime(d.last_success_at)}`
    : 'Nothing delivered yet';
  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.secondary">
        {lastSuccess}
      </Typography>
      {d.consecutive_failures > 0 && (
        <Typography variant="caption" color="error">
          {d.consecutive_failures === 1
            ? '1 failure'
            : `${d.consecutive_failures} failures in a row`}
          {!d.paused && d.next_attempt_at
            ? `, next try ${formatTime(d.next_attempt_at)}`
            : ''}
        </Typography>
      )}
      {d.last_error && (
        <Tooltip title={d.last_error}>
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ ...monoSx, wordBreak: 'normal', display: 'block' }}
          >
            {formatTime(d.last_error_at)} {d.last_error}
          </Typography>
        </Tooltip>
      )}
    </Stack>
  );
}

export default function DestinationsList({
  destinations,
  testing,
  onTest,
  onSetPaused,
  onDelete,
}: DestinationsListProps) {
  const [confirm, setConfirm] = React.useState<AuditDestination | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const handleDelete = async () => {
    if (!confirm) return;
    setDeleting(true);
    try {
      await onDelete(confirm);
      setConfirm(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Box sx={listSx} role="list" aria-label="Streaming destinations">
        {destinations.map(d => {
          const status = STATUS_CHIPS[destinationStatus(d)];
          const isTesting = testing.has(d.id);
          return (
            <Box
              key={d.id}
              role="listitem"
              sx={{ ...listRowSx, alignItems: 'flex-start', py: 1.5 }}
            >
              <KindTile kind={d.kind} />
              <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle2" noWrap sx={{ flex: 1 }}>
                    {d.name}
                  </Typography>
                  <Tooltip title={status.hint}>
                    <span>
                      <StatusPill tone={status.tone}>{status.label}</StatusPill>
                    </span>
                  </Tooltip>
                </Box>
                <Box sx={{ display: 'flex', gap: 0.75, minWidth: 0 }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ flexShrink: 0 }}
                  >
                    {kindLabel(d.kind)}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={monoSx}
                  >
                    {destinationTarget(d)}
                  </Typography>
                </Box>
                <Health destination={d} />
                <Box sx={{ display: 'flex', gap: 0.5, ml: -1 }}>
                  <Tooltip title="Send a test event">
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => onTest(d)}
                        disabled={isTesting}
                        aria-label={`Send a test event to ${d.name}`}
                      >
                        {isTesting ? (
                          <CircularProgress size={16} />
                        ) : (
                          <SendIcon fontSize="small" />
                        )}
                      </IconButton>
                    </span>
                  </Tooltip>
                  {d.paused ? (
                    <Tooltip title="Resume">
                      <IconButton
                        size="small"
                        onClick={() => onSetPaused(d, false)}
                        aria-label={`Resume ${d.name}`}
                      >
                        <ResumeIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  ) : (
                    <Tooltip title="Pause">
                      <IconButton
                        size="small"
                        onClick={() => onSetPaused(d, true)}
                        aria-label={`Pause ${d.name}`}
                      >
                        <PauseIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setConfirm(d)}
                      aria-label={`Delete ${d.name}`}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Stack>
            </Box>
          );
        })}
      </Box>

      <Dialog
        open={confirm !== null}
        onClose={() => !deleting && setConfirm(null)}
        maxWidth="xs"
        fullWidth
      >
        {confirm && (
          <>
            <DialogTitle>Delete destination?</DialogTitle>
            <DialogContent>
              <DialogContentText>
                {confirm.name} stops receiving audit events and its credentials
                are removed. There is no undo. To stop for a while instead,
                pause it.
              </DialogContentText>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setConfirm(null)} disabled={deleting}>
                Cancel
              </Button>
              <Button
                variant="contained"
                color="error"
                onClick={handleDelete}
                disabled={deleting}
                startIcon={
                  deleting ? <CircularProgress size={16} /> : undefined
                }
              >
                Delete
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </>
  );
}
