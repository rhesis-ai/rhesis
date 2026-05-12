'use client';

/**
 * One-shot client-secret reveal dialog.
 *
 * Shown immediately after a successful create or rotate. The
 * plaintext secret is the **only** thing we render that the user
 * cannot get back any other way -- if they close this dialog
 * without copying the secret, the only recovery is another rotation
 * (which invalidates the previous secret entirely).
 *
 * Design choices:
 *
 * - **Non-dismissible chrome.** The dialog has no `onClose` on the
 *   backdrop / Escape key. The only way out is the explicit
 *   acknowledgement button. This stops the operator from absent-mindedly
 *   clicking outside and losing the secret.
 * - **Confirmation required.** A checkbox must be ticked before the
 *   acknowledgement button enables. Forces a deliberate action so
 *   the workflow has a clear "I have copied the secret" moment.
 * - **Copy-to-clipboard right next to the value.** No mouse-drag
 *   selection of a long URL-safe string -- a copy button avoids
 *   transcription mistakes and avoids leaving the value in the
 *   selection clipboard longer than necessary.
 * - **Monospace + breakable.** The secret is `secrets.token_urlsafe(32)`
 *   on the backend, which has no obvious break points; rendering it
 *   monospace + word-break-all keeps it visually contained without
 *   horizontal scrolling.
 */

import * as React from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { ContentCopy as CopyIcon } from '@mui/icons-material';
import { useNotifications } from '@/components/common/NotificationContext';

interface ClientSecretDisplayDialogProps {
  open: boolean;
  clientId: string;
  clientSecret: string;
  /**
   * Called when the user explicitly acknowledges they have saved
   * the secret. The parent should treat this as the close handler;
   * the dialog itself does not provide a "cancel" path.
   */
  onAcknowledge: () => void;
  /**
   * Title override -- defaults to a "Save your client secret" wording
   * that fits both the create flow and the rotate flow. Pass an
   * explicit title for the rotate case so the user knows the previous
   * secret has stopped working.
   */
  title?: string;
}

export default function ClientSecretDisplayDialog({
  open,
  clientId,
  clientSecret,
  onAcknowledge,
  title = 'Save your client secret',
}: ClientSecretDisplayDialogProps) {
  const notifications = useNotifications();
  const [acknowledged, setAcknowledged] = React.useState(false);

  // Reset the checkbox each time a new secret arrives so the user
  // always has to re-acknowledge. Otherwise a stale `true` from a
  // previous rotation would let them dismiss without seeing the new
  // one.
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
    <Dialog
      open={open}
      // Disable backdrop / escape close so the only exit is the
      // acknowledgement button -- the secret is unrecoverable, the
      // friction is the point.
      disableEscapeKeyDown
      maxWidth="sm"
      fullWidth
      // Note: MUI's Dialog has no built-in disableBackdropClick; we
      // ignore the onClose argument when the reason is backdrop or
      // escape. (MUI v5+ pattern.)
      onClose={(_event, reason) => {
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
          return;
        }
      }}
    >
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Alert severity="warning">
            This is the only time you will see this secret. Store it in
            your secrets manager now -- if you lose it, you will need
            to rotate the client to issue a new one.
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
      </DialogContent>
      <DialogActions>
        <Button
          variant="contained"
          color="primary"
          disabled={!acknowledged}
          onClick={onAcknowledge}
        >
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}
