'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import { useCreateAuditExport } from '../hooks/useAuditExports';
import { AuditExportFormat } from '../types';

const FORMAT_OPTIONS = [
  {
    value: AuditExportFormat.JSONL,
    label: 'JSON Lines',
    description: 'One event per line, exactly as the API returns it.',
  },
  {
    value: AuditExportFormat.CSV,
    label: 'CSV',
    description: 'For spreadsheets. Changes are kept as JSON in one column.',
  },
] as const;

interface AuditExportDialogProps {
  open: boolean;
  onClose: () => void;
  /** The Events list's `$filter`; undefined exports the whole log. */
  filter?: string;
}

export default function AuditExportDialog({
  open,
  onClose,
  filter,
}: AuditExportDialogProps) {
  const [format, setFormat] = React.useState<AuditExportFormat>(
    AuditExportFormat.JSONL
  );
  const create = useCreateAuditExport();
  const { show } = useNotifications();

  const close = () => {
    create.reset();
    onClose();
  };

  const start = () =>
    create.mutate(
      { format, ...(filter ? { filter } : {}) },
      {
        onSuccess: () => {
          show(
            'Export started. Download it from the Exports section when it is ready.',
            { severity: 'success' }
          );
          close();
        },
      }
    );

  return (
    <Dialog open={open} onClose={close} maxWidth="xs" fullWidth>
      <DialogTitle>Export audit log</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {filter
            ? 'Exports every event that matches the current search and filters, not just this page.'
            : 'Exports every event in the log.'}{' '}
          The export runs in the background and is recorded in the log.
        </Typography>
        <RadioGroup
          aria-label="Export format"
          value={format}
          onChange={e => setFormat(e.target.value as AuditExportFormat)}
        >
          {FORMAT_OPTIONS.map(option => (
            <FormControlLabel
              key={option.value}
              value={option.value}
              control={<Radio />}
              label={
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="body2">{option.label}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.description}
                  </Typography>
                </Box>
              }
              sx={{ alignItems: 'flex-start', mb: 1 }}
            />
          ))}
        </RadioGroup>
        {create.error && (
          <Alert severity="error" sx={{ mt: 1 }}>
            {getApiErrorMessage(create.error, 'Could not start the export.')}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Cancel</Button>
        <Button variant="contained" onClick={start} disabled={create.isPending}>
          {create.isPending ? 'Starting…' : 'Export'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
