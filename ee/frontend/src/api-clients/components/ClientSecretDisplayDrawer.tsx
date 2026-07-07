'use client';

/**
 * One-shot client-secret reveal drawer.
 *
 * Shown immediately after a successful create or rotate. The
 * plaintext secret is the **only** thing we render that the user
 * cannot get back any other way -- if they close this drawer
 * without copying the secret, the only recovery is another rotation
 * (which invalidates the previous secret entirely).
 *
 * Design choices:
 *
 * - **Non-dismissible chrome.** The drawer has no backdrop / Escape
 *   close. The only way out is the explicit acknowledgement button.
 * - **Confirmation required.** A checkbox must be ticked before the
 *   acknowledgement button enables.
 * - **Copy-to-clipboard right next to the value.**
 */

import * as React from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Drawer,
  FormControlLabel,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { ContentCopy as CopyIcon } from '@mui/icons-material';
import { useNotifications } from '@/components/common/NotificationContext';
import { BACKDROP_COLORS } from '@/styles/theme';
import {
  drawerFooterSaveButtonSx,
  DRAWER_WIDTH,
} from '@/components/common/drawerFormFieldSx';

interface ClientSecretDisplayDrawerProps {
  open: boolean;
  clientId: string;
  clientSecret: string;
  onAcknowledge: () => void;
  title?: string;
}

export default function ClientSecretDisplayDrawer({
  open,
  clientId,
  clientSecret,
  onAcknowledge,
  title = 'Save your client secret',
}: ClientSecretDisplayDrawerProps) {
  const notifications = useNotifications();
  const [acknowledged, setAcknowledged] = React.useState(false);

  React.useEffect(() => {
    if (open) setAcknowledged(false);
  }, [open, clientSecret]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(clientSecret);
      notifications.show('Client secret copied to clipboard', {
        severity: 'success',
        autoHideDuration: 3000,
      });
    } catch {
      notifications.show(
        'Could not access the clipboard. Copy the secret manually.',
        { severity: 'warning', autoHideDuration: 5000 }
      );
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      variant="temporary"
      disableEscapeKeyDown
      onClose={(_event, reason) => {
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
          return;
        }
      }}
      PaperProps={{
        sx: {
          width: DRAWER_WIDTH,
          display: 'flex',
          flexDirection: 'column',
          p: '30px',
          gap: '40px',
          boxSizing: 'border-box',
        },
      }}
      sx={{
        '& .MuiBackdrop-root': {
          backgroundColor: BACKDROP_COLORS.create,
        },
      }}
    >
      <Box sx={{ flexShrink: 0 }}>
        <Typography
          sx={{
            fontSize: 23,
            fontWeight: 700,
            lineHeight: '27.6px',
            color: theme => theme.palette.greyscale.title,
          }}
        >
          {title}
        </Typography>
      </Box>

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '30px',
        }}
      >
        <Stack spacing={2}>
          <Alert severity="warning">
            This is the only time you will see this secret. Store it in your
            secrets manager now -- if you lose it, you will need to rotate the
            client to issue a new one.
          </Alert>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Client ID
            </Typography>
            <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
              {clientId}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Client secret
            </Typography>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1,
                p: 1.5,
                bgcolor: 'action.hover',
                borderRadius: theme => `${theme.shape.borderRadius}px`,
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                  flexGrow: 1,
                }}
              >
                {clientSecret}
              </Typography>
              <Tooltip title="Copy secret to clipboard">
                <IconButton size="small" onClick={handleCopy} aria-label="Copy">
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={acknowledged}
                onChange={e => setAcknowledged(e.target.checked)}
              />
            }
            label="I have saved the client secret in a safe place."
          />
        </Stack>
      </Box>

      <Box sx={{ flexShrink: 0, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          color="primary"
          disabled={!acknowledged}
          onClick={onAcknowledge}
          sx={drawerFooterSaveButtonSx}
        >
          Done
        </Button>
      </Box>
    </Drawer>
  );
}
