'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { ContentCopy as CopyIcon } from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { STANDARD_WEBHOOKS_URL } from '../destinations';
import { monoSx } from './AuditChanges';

interface SigningSecretDrawerProps {
  open: boolean;
  destinationName: string;
  secret: string;
  onAcknowledge: () => void;
}

function ignoreClose() {
  // Only "Done" closes it, so the secret cannot be lost to a stray click.
}

/** The webhook signing secret, shown once after create. */
export default function SigningSecretDrawer({
  open,
  destinationName,
  secret,
  onAcknowledge,
}: SigningSecretDrawerProps) {
  const notifications = useNotifications();
  const [acknowledged, setAcknowledged] = React.useState(false);

  React.useEffect(() => {
    if (open) setAcknowledged(false);
  }, [open, secret]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      notifications.show('Signing secret copied', {
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
    <BaseDrawer
      open={open}
      onClose={ignoreClose}
      title="Save your signing secret"
      onSave={onAcknowledge}
      saveButtonText="Done"
      saveDisabled={!acknowledged}
      closeButtonText=""
    >
      <Stack spacing={2}>
        <Alert severity="warning">
          You won&apos;t see this secret again. Store it in your secrets manager
          now. If you lose it, delete the destination and add it again.
        </Alert>

        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Destination
          </Typography>
          <Typography variant="body1">{destinationName}</Typography>
        </Box>

        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Signing secret
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1,
              p: 1.5,
              bgcolor: 'action.hover',
              borderRadius: BORDER_RADIUS.sm,
            }}
          >
            <Typography
              variant="body2"
              sx={{ ...monoSx, wordBreak: 'break-all', flexGrow: 1 }}
            >
              {secret}
            </Typography>
            <Tooltip title="Copy secret">
              <IconButton
                size="small"
                onClick={handleCopy}
                aria-label="Copy signing secret"
              >
                <CopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Typography variant="body2" color="text.secondary">
          Every request is signed with{' '}
          <Link href={STANDARD_WEBHOOKS_URL} target="_blank" rel="noopener">
            Standard Webhooks
          </Link>
          . Use this secret to verify the <code>webhook-signature</code> header
          before you trust a request.
        </Typography>

        <FormControlLabel
          control={
            <Checkbox
              checked={acknowledged}
              onChange={e => setAcknowledged(e.target.checked)}
            />
          }
          label="I have saved the signing secret in a safe place."
        />
      </Stack>
    </BaseDrawer>
  );
}
