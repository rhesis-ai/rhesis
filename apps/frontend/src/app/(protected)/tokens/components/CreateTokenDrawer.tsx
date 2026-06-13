'use client';

import React, { useState, useEffect } from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
} from '@mui/material';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import dayjs from 'dayjs';
import BaseDrawer from '@/components/common/BaseDrawer';

interface CreateTokenDrawerProps {
  open: boolean;
  onClose: () => void;
  onCreateToken: (
    name: string,
    expiresInDays: number | null
  ) => Promise<TokenResponse>;
}

export default function CreateTokenDrawer({
  open,
  onClose,
  onCreateToken,
}: CreateTokenDrawerProps) {
  const [name, setName] = useState('');
  const [expiryOption, setExpiryOption] = useState<
    '30' | '60' | '90' | 'custom' | 'never'
  >('30');
  const [customDate, setCustomDate] = useState<dayjs.Dayjs | null>(
    dayjs().add(1, 'day')
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setExpiryOption('30');
      setCustomDate(dayjs().add(1, 'day'));
      setLoading(false);
    }
  }, [open]);

  const handleClose = () => {
    setName('');
    setExpiryOption('30');
    setCustomDate(dayjs().add(1, 'day'));
    onClose();
  };

  const handleSave = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) return;

    try {
      setLoading(true);
      let expiresInDays: number | null = null;

      if (expiryOption === 'custom' && customDate) {
        const diffDays = customDate.diff(dayjs(), 'day');
        expiresInDays = Math.max(1, diffDays);
      } else if (expiryOption !== 'never') {
        expiresInDays = parseInt(expiryOption, 10);
      }

      await onCreateToken(trimmedName, expiresInDays);
      handleClose();
    } catch {
      // Parent handles errors
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Create New Token"
      onSave={handleSave}
      saveButtonText="Create"
      saveDisabled={!name.trim() || loading}
      loading={loading}
    >
      <Stack spacing={3}>
        <TextField
          autoFocus
          label="Token Name"
          fullWidth
          value={name}
          onChange={e => setName(e.target.value)}
          required
          disabled={loading}
        />
        <FormControl fullWidth disabled={loading}>
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
              disabled={loading}
              slotProps={{
                textField: {
                  required: true,
                  fullWidth: true,
                },
              }}
            />
          </LocalizationProvider>
        )}
      </Stack>
    </BaseDrawer>
  );
}
