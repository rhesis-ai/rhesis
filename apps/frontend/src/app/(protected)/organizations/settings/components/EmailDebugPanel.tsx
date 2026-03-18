'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Typography,
  Stack,
  Chip,
  Divider,
  Alert,
  CircularProgress,
  FormControlLabel,
  Switch,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface EmailDebugPanelProps {
  organizationId: string;
  sessionToken: string;
}

type SendState = 'idle' | 'sending' | 'success' | 'error';

interface EmailResult {
  day_1?: string;
  day_2?: string;
  day_3?: string;
}

function statusColor(
  result: string | undefined
): 'default' | 'success' | 'error' | 'warning' {
  if (!result) return 'default';
  if (result === 'scheduled' || result === 'simulated') return 'success';
  if (result === 'error') return 'error';
  return 'warning';
}

export default function EmailDebugPanel({
  organizationId,
  sessionToken,
}: EmailDebugPanelProps) {
  const [simulate, setSimulate] = React.useState(true);
  const [state, setState] = React.useState<SendState>('idle');
  const [results, setResults] = React.useState<EmailResult | null>(null);
  const [recipient, setRecipient] = React.useState<string>('');
  const [message, setMessage] = React.useState<string>('');
  const [errorMsg, setErrorMsg] = React.useState<string>('');

  const handleTrigger = async () => {
    setState('sending');
    setResults(null);
    setErrorMsg('');
    setMessage('');

    try {
      const client = new ApiClientFactory(
        sessionToken
      ).getOrganizationsClient();
      const response = await client.triggerTestEmails(organizationId, simulate);
      setResults(response.results as EmailResult);
      setRecipient(response.recipient);
      setMessage(response.message);
      setState('success');
    } catch (err: unknown) {
      setState('error');
      setErrorMsg(
        err instanceof Error ? err.message : 'Failed to trigger test emails'
      );
    }
  };

  return (
    <Box>
      <Typography variant="subtitle1" fontWeight="medium" gutterBottom>
        Onboarding Email Test Trigger
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Sends Day 1 / Day 2 / Day 3 onboarding emails to your account with short
        delays (1 min / 2 min / 3 min) instead of 24 h / 48 h / 72 h. Check your
        backend console logs for the full SendGrid payload.
      </Typography>

      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Switch
              checked={simulate}
              onChange={e => setSimulate(e.target.checked)}
              color="warning"
              size="small"
            />
          }
          label={
            <Typography variant="body2">
              <strong>Simulate only</strong> — log payload to console, skip
              actual SendGrid call
            </Typography>
          }
        />

        <Box>
          <Button
            variant="outlined"
            color={simulate ? 'warning' : 'primary'}
            size="small"
            onClick={handleTrigger}
            disabled={state === 'sending'}
            startIcon={
              state === 'sending' ? (
                <CircularProgress size={14} color="inherit" />
              ) : null
            }
          >
            {state === 'sending'
              ? 'Working…'
              : simulate
                ? 'Simulate Day 1 / Day 2 / Day 3 emails'
                : 'Send Day 1 (+1 min) / Day 2 (+2 min) / Day 3 (+3 min)'}
          </Button>
        </Box>
      </Stack>

      {state === 'success' && results && (
        <Box mt={2}>
          <Typography variant="caption" color="text.secondary">
            Recipient: <strong>{recipient}</strong>
          </Typography>
          <Stack direction="row" spacing={1} mt={1} flexWrap="wrap">
            {(['day_1', 'day_2', 'day_3'] as const).map((key, i) => (
              <Chip
                key={key}
                label={`Day ${i + 1}: ${results[key] ?? 'unknown'}`}
                color={statusColor(results[key])}
                size="small"
                variant="outlined"
              />
            ))}
          </Stack>
          <Alert
            severity={simulate ? 'info' : 'success'}
            sx={{ mt: 1.5 }}
            variant="outlined"
          >
            {message}
            {simulate && (
              <>
                <br />
                Check your backend console (stdout) to see the full SendGrid
                payload.
              </>
            )}
          </Alert>
        </Box>
      )}

      {state === 'error' && (
        <Alert severity="error" sx={{ mt: 2 }} variant="outlined">
          {errorMsg}
        </Alert>
      )}

      <Divider sx={{ mt: 3 }} />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ mt: 1, display: 'block' }}
      >
        This panel is for development debugging and can be removed once email
        delivery is verified.
      </Typography>
    </Box>
  );
}
