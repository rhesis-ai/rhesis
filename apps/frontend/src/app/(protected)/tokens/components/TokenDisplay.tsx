'use client';

import { Box, TextField, Typography, IconButton, Alert } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseDrawer from '@/components/common/BaseDrawer';
import { formatDate } from '@/utils/date';

interface TokenDisplayProps {
  open: boolean;
  onClose: () => void;
  token: TokenResponse | null;
  title?: string;
}

export default function TokenDisplay({
  open,
  onClose,
  token,
  title = 'Your New API Token',
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
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      closeButtonText="Close"
    >
      {token && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              Token Name
            </Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {token.name}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              Expires
            </Typography>
            <Typography variant="body1">
              {token.expires_at ? formatDate(token.expires_at) : 'Never'}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Access Token
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                fullWidth
                value={token.access_token}
                variant="outlined"
                InputProps={{ readOnly: true }}
                inputProps={{
                  style: { fontFamily: 'monospace', fontSize: 13 },
                }}
              />
              <IconButton
                onClick={handleCopyToken}
                color="primary"
                aria-label="Copy token"
              >
                <ContentCopyIcon />
              </IconButton>
            </Box>
          </Box>

          <Alert severity="info">
            Store this token securely — it won&apos;t be shown again. If you
            lose it, you&apos;ll need to generate a new one.
          </Alert>
        </Box>
      )}
    </BaseDrawer>
  );
}
