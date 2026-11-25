'use client';

import { useEffect, useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Radio,
  RadioGroup,
  Typography,
} from '@mui/material';

export interface ScopeOption<T extends string> {
  value: T;
  label: string;
  description: string;
  /** Shown instead of the description when the option can't be picked. */
  disabledReason?: string;
}

interface Props<T extends string> {
  open: boolean;
  title: string;
  options: ScopeOption<T>[];
  initial: T;
  confirmText: string;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: (value: T) => void;
}

/** "This run only / This and following runs / The whole schedule", like a calendar. */
export default function ScheduleScopeDialog<T extends string>({
  open,
  title,
  options,
  initial,
  confirmText,
  destructive = false,
  onCancel,
  onConfirm,
}: Props<T>) {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    if (open) setValue(initial);
  }, [open, initial]);

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <RadioGroup
          value={value}
          onChange={event => setValue(event.target.value as T)}
        >
          {options.map(option => (
            <FormControlLabel
              key={option.value}
              value={option.value}
              disabled={Boolean(option.disabledReason)}
              control={<Radio />}
              sx={{ alignItems: 'flex-start', mb: 1 }}
              label={
                <>
                  <Typography variant="body2">{option.label}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.disabledReason ?? option.description}
                  </Typography>
                </>
              }
            />
          ))}
        </RadioGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button
          variant="contained"
          color={destructive ? 'error' : 'primary'}
          onClick={() => onConfirm(value)}
        >
          {confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
