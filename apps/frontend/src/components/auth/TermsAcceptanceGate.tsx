'use client';

import * as React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import TermsAcceptanceField from './TermsAcceptanceField';
import { acceptTerms, fetchTermsStatus } from '@/utils/api-client/auth-client';
import { fetchQuickStartEnabled } from '@/utils/quick_start';

/**
 * Global post-login gate: if the active terms version changed since the user last
 * accepted, we block the app until they accept the new version.
 *
 * Skipped in Quick Start mode — local dev auto-login should not be blocked.
 */
export default function TermsAcceptanceGate() {
  const { status } = useSession();

  const [quickStart, setQuickStart] = React.useState<boolean | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [open, setOpen] = React.useState(false);
  const [checked, setChecked] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showWarning, setShowWarning] = React.useState(false);
  const [hasPriorAcceptance, setHasPriorAcceptance] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;

    fetchQuickStartEnabled().then(enabled => {
      if (!cancelled) {
        setQuickStart(enabled);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (quickStart === true) {
      setLoading(false);
      return;
    }

    if (quickStart === null || status !== 'authenticated') {
      if (quickStart !== null) {
        setLoading(false);
      }
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetchTermsStatus()
      .then(status => {
        if (cancelled) return;
        setHasPriorAcceptance(status.has_prior_acceptance);
        setOpen(!status.terms_accepted);
      })
      .catch(() => {
        // Fail open when the status endpoint is unreachable (transient outage,
        // local dev). A definitive `terms_accepted: false` from a 200 still
        // blocks until acceptance — only transport/API failures bypass the gate.
        if (cancelled) return;
        setOpen(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, quickStart]);

  if (
    loading ||
    quickStart === null ||
    quickStart ||
    status !== 'authenticated'
  ) {
    return null;
  }

  const handleAccept = async () => {
    setError(null);

    if (!checked) {
      setShowWarning(true);
      return;
    }

    try {
      setSubmitting(true);
      await acceptTerms();
      setOpen(false);
    } catch {
      setError('Failed to record terms acceptance. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={(_, reason) => {
        // Non-dismissable: require explicit acceptance.
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') return;
      }}
      disableEscapeKeyDown
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        {hasPriorAcceptance ? 'Updated Terms' : 'Terms and Conditions'}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {hasPriorAcceptance
              ? 'We’ve updated our Terms and Privacy Policy. Please accept to continue.'
              : 'Please review and accept our Terms and Privacy Policy to continue.'}
          </Typography>

          <TermsAcceptanceField
            checked={checked}
            onChange={next => {
              setChecked(next);
              if (next) setShowWarning(false);
            }}
            showWarning={showWarning}
          />

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          variant="contained"
          onClick={handleAccept}
          disabled={submitting}
        >
          {submitting ? 'Saving…' : 'Accept and continue'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
