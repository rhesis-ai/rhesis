import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
} from '@mui/material';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';

interface RefreshTokenModalProps {
  open: boolean;
  onClose: () => void;
  onRefresh: (expiresInDays: number | null) => Promise<void>;
  tokenName: string;
}

export default function RefreshTokenModal({
  open,
  onClose,
  onRefresh,
  tokenName,
}: RefreshTokenModalProps) {
  const [expiryOption, setExpiryOption] = useState<
    '30' | '60' | '90' | 'custom' | 'never'
  >('30');
  const [customDate, setCustomDate] = useState<dayjs.Dayjs | null>(
    dayjs().add(1, 'day')
  );

  const handleClose = () => {
    setExpiryOption('30');
    setCustomDate(dayjs().add(1, 'day'));
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    let expiresInDays: number | null = null;

    if (expiryOption === 'custom' && customDate) {
      const diffDays = customDate.diff(dayjs(), 'day');
      expiresInDays = Math.max(1, diffDays);
    } else if (expiryOption !== 'never') {
      expiresInDays = parseInt(expiryOption);
    }

    await onRefresh(expiresInDays);
    handleClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Invalidate and Refresh Token</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2 }}>
            {tokenName}
          </Typography>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
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
            OK
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
