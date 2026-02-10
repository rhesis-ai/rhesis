'use client';

import {
  Box,
  Button,
  TextField,
  Typography,
  IconButton,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CelebrationIcon from '@mui/icons-material/Celebration';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import { useNotifications } from '@/components/common/NotificationContext';

interface TokenDisplayProps {
  open: boolean;
  onClose: () => void;
  token: TokenResponse | null;
}

export default function TokenDisplay({
  open,
  onClose,
  token,
}: TokenDisplayProps) {
  const notifications = useNotifications();

  const handleCopyToken = async () => {
    try {
      if (token) {
        await navigator.clipboard.writeText(token.access_token);
        notifications.show('Token copied to clipboard!', {
          severity: 'success',
        });
      }
    } catch (_err) {
      notifications.show('Failed to copy token to clipboard', {
        severity: 'error',
      });
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CelebrationIcon color="primary" />
        Your New API Token
      </DialogTitle>
      <DialogContent>
        {token && (
          <>
            <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'bold' }}>
              Token Name: {token.name}
            </Typography>
            <Typography variant="subtitle2" sx={{ mb: 2 }}>
              Expires:{' '}
              {token.expires_at
                ? new Date(token.expires_at).toLocaleDateString()
                : 'Never'}
            </Typography>
            <Typography color="warning.main" sx={{ mb: 2 }}>
              Store this token securely - it won&apos;t be shown again. If you
              lose it, you&apos;ll need to generate a new one.
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                fullWidth
                value={token.access_token}
                variant="outlined"
                InputProps={{
                  readOnly: true,
                }}
              />
              <IconButton onClick={handleCopyToken} color="primary">
                <ContentCopyIcon />
              </IconButton>
            </Box>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
