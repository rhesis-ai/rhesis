'use client';

import { useState } from 'react';
import {
  Alert,
  AlertTitle,
  Button,
  Collapse,
  CircularProgress,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function VerificationBanner() {
  const { data: session } = useSession();
  const [dismissed, setDismissed] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const user = session?.user;
  const isEmailVerified = user?.is_email_verified ?? true;

  // Don't show if verified, dismissed, or no session
  if (isEmailVerified || dismissed || !user?.email) {
    return null;
  }

  const handleResend = async () => {
    setResending(true);
    try {
      await fetch(`${getClientApiBaseUrl()}/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email }),
      });
      setResent(true);
    } catch {
      // silently fail
    } finally {
      setResending(false);
    }
  };

  return (
    <Collapse in={!dismissed}>
      <Alert
        severity="info"
        onClose={() => setDismissed(true)}
        action={
          !resent ? (
            <Button
              color="inherit"
              size="small"
              onClick={handleResend}
              disabled={resending}
              startIcon={resending ? <CircularProgress size={14} /> : undefined}
            >
              Resend
            </Button>
          ) : undefined
        }
        sx={{ borderRadius: 0 }}
      >
        <AlertTitle sx={{ mb: 0 }}>
          {resent
            ? 'Verification email sent! Check your inbox.'
            : 'Please verify your email address. Check your inbox for a verification link.'}
        </AlertTitle>
      </Alert>
    </Collapse>
  );
}
