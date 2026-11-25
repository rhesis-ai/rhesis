'use client';

import { useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { getApiErrorMessage } from '@/utils/error-utils';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';
import { useScheduleActions } from './useSchedules';

interface Props {
  schedule: TestRunSchedule | null;
  onClose: () => void;
}

/** Become a schedule's owner. When a model the runs need isn't available to you, nothing changes. */
export default function TakeOverDialog({ schedule, onClose }: Props) {
  const actions = useScheduleActions();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setError(null);
    onClose();
  };

  const confirm = async () => {
    if (!schedule) return;
    setBusy(true);
    try {
      await new ApiClientFactory()
        .getTestRunSchedulesClient()
        .takeOver(schedule.id);
      await actions.refresh();
      close();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not take it over.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={Boolean(schedule)} onClose={close} maxWidth="xs" fullWidth>
      <DialogTitle>Take over {schedule?.name}?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Runs will execute as you and use your model access.
        </DialogContentText>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Cancel</Button>
        <Button variant="contained" onClick={confirm} disabled={busy}>
          Take over
        </Button>
      </DialogActions>
    </Dialog>
  );
}
