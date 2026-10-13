'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import {
  Delete as DeleteIcon,
  Pause as PauseIcon,
  PlayArrow as ResumeIcon,
  Send as SendIcon,
} from '@mui/icons-material';
import {
  DestinationStatus,
  destinationStatus,
  destinationTarget,
  kindLabel,
  type AuditDestination,
} from '../destinations';
import { monoSx } from './AuditChanges';

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
  { label: string; color: 'success' | 'default' | 'error'; hint: string }
> = {
  active: {
    label: 'Active',
    color: 'success',
    hint: 'New events are sent within seconds.',
  },
  paused: {
    label: 'Paused',
    color: 'default',
    hint: 'Nothing is sent. Resume to continue from the last delivered event.',
  },
  auto_paused: {
    label: 'Auto-paused',
    color: 'error',
    hint:
      'Paused itself after failing for about 13 hours. Fix the receiver, ' +
      'then resume to continue from the last delivered event.',
  },
};

function formatTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '';
}

function Health({ destination: d }: { destination: AuditDestination }) {
  const lastSuccess = d.last_success_at
    ? `Last delivered ${formatTime(d.last_success_at)}`
    : 'Nothing delivered yet';
  return (
    <Stack spacing={0.25}>
      <Typography variant="body2">{lastSuccess}</Typography>
      {d.consecutive_failures > 0 && (
        <Typography variant="body2" color="error">
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
      <TableContainer>
        <Table size="small" sx={{ tableLayout: 'fixed' }}>
          <TableHead>
            <TableRow>
              <TableCell>Destination</TableCell>
              <TableCell sx={{ width: '15%' }}>Status</TableCell>
              <TableCell sx={{ width: '35%' }}>Health</TableCell>
              <TableCell align="right" sx={{ width: '15%' }}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {destinations.map(d => {
              const status = STATUS_CHIPS[destinationStatus(d)];
              const isTesting = testing.has(d.id);
              return (
                <TableRow key={d.id} hover>
                  <TableCell>
                    <Stack spacing={0.25}>
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <Typography variant="body2" noWrap>
                          {d.name}
                        </Typography>
                        <Chip
                          label={kindLabel(d.kind)}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={monoSx}
                      >
                        {destinationTarget(d)}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Tooltip title={status.hint}>
                      <Chip
                        label={status.label}
                        size="small"
                        color={status.color}
                      />
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Health destination={d} />
                  </TableCell>
                  <TableCell align="right">
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
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

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
