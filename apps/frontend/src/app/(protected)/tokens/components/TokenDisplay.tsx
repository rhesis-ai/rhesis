'use client';

import { Box, TextField, Typography, IconButton } from '@mui/material';
import { alpha } from '@mui/material/styles';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CelebrationIcon from '@mui/icons-material/Celebration';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseDrawer from '@/components/common/BaseDrawer';
import { BORDER_RADIUS } from '@/styles/theme-constants';

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
      titleIcon={<CelebrationIcon color="primary" />}
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
              {token.expires_at
                ? new Date(token.expires_at).toLocaleDateString()
                : 'Never'}
            </Typography>
          </Box>

          {/* Figma Info Alert — node 1299:16000 (blue variant) */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              bgcolor: theme => alpha(theme.palette.primary.main, 0.1),
              borderRadius: BORDER_RADIUS.xs,
              px: '30px',
              py: '12px',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ flexShrink: 0, pt: '7px', pr: '12px' }}>
              <InfoOutlinedIcon sx={{ fontSize: 22, color: 'primary.main' }} />
            </Box>
            <Box sx={{ flex: 1, py: '8px' }}>
              <Typography
                sx={{
                  fontSize: 16,
                  fontWeight: 400,
                  lineHeight: '24px',
                  color: 'primary.main',
                }}
              >
                Store this token securely — it won&apos;t be shown again. If you
                lose it, you&apos;ll need to generate a new one.
              </Typography>
            </Box>
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
        </Box>
      )}
    </BaseDrawer>
  );
}
