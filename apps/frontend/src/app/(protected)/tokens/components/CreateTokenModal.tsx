'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import dayjs from 'dayjs';

interface CreateTokenModalProps {
  open: boolean;
  onClose: () => void;
  onCreateToken: (
    name: string,
    expiresInDays: number | null
  ) => Promise<TokenResponse>;
}

export default function CreateTokenModal({
  open,
  onClose,
  onCreateToken,
}: CreateTokenModalProps) {
  const [name, setName] = useState('');
  const [expiryOption, setExpiryOption] = useState<
    '30' | '60' | '90' | 'custom' | 'never'
  >('30');
  const [customDate, setCustomDate] = useState<dayjs.Dayjs | null>(
    dayjs().add(1, 'day')
  );

  useEffect(() => {
    if (open) {
      setName('');
      setExpiryOption('30');
      setCustomDate(dayjs().add(1, 'day'));
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let expiresInDays: number | null = null;

      if (expiryOption === 'custom' && customDate) {
        const diffDays = customDate.diff(dayjs(), 'day');
        expiresInDays = Math.max(1, diffDays);
      } else if (expiryOption !== 'never') {
        expiresInDays = parseInt(expiryOption);
      }

      await onCreateToken(name, expiresInDays);
      handleClose();
    } catch (error) {}
  };

  const handleClose = () => {
    setName('');
    setExpiryOption('30');
    setCustomDate(dayjs().add(1, 'day'));
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Create New Token</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              autoFocus
              label="Token Name"
              fullWidth
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
            <FormControl fullWidth>
              <InputLabel>Token Expiration</InputLabel>
              <Select
                value={expiryOption}
                label="Token Expiration"
                onChange={e =>
                  setExpiryOption(e.target.value as typeof expiryOption)
                }
              >
                <MenuItem value="30">30 days</MenuItem>
                <MenuItem value="60">60 days</MenuItem>
                <MenuItem value="90">90 days</MenuItem>
                <MenuItem value="custom">Custom date</MenuItem>
                <MenuItem value="never">Never expire</MenuItem>
              </Select>
            </FormControl>
            {expiryOption === 'custom' && (
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="Expiration Date"
                  value={customDate}
                  onChange={newValue => setCustomDate(newValue)}
                  minDate={dayjs().add(1, 'day')}
                  slotProps={{
                    textField: {
                      required: true,
                      fullWidth: true,
                    },
                  }}
                />
              </LocalizationProvider>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button type="submit" variant="contained">
            Create
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
