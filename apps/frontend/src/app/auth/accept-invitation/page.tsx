'use client';

import { useEffect, useState } from 'react';
import { Typography, CircularProgress, Alert, Button } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { getBaseUrl } from '@/utils/url-resolver';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { useAuthStyles } from '@/components/auth/useAuthStyles';
import { rem } from '@/styles/theme-constants';

/**
 * Landing page for an organization invitation link.
 *
 * The invited person joins the organization only here, by opening the link
 * sent to their mailbox. Consuming the token both records their acceptance and
 * signs them in, so they land in the app already a member.
 */
export default function AcceptInvitationPage() {
  const { heading, primaryButton } = useAuthStyles();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'error'>('loading');
  const [message, setMessage] = useState('Joining your organization...');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid or missing invitation token.');
      return;
    }

    const accept = async () => {
      try {
        const response = await fetch(`${getBaseUrl()}/auth/accept-invitation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Could not accept the invitation');
        }

        if (data.auth_code) {
          const result = await signIn('credentials', {
            code: data.auth_code,
            redirect: false,
          });

          if (result?.error) {
            throw new Error(result.error);
          }

          window.location.href = '/architect';
          return;
        }

        throw new Error('No auth code received');
      } catch (err) {
        setStatus('error');
        setMessage(
          err instanceof Error ? err.message : 'Could not accept the invitation'
        );
      }
    };

    accept();
  }, [token]);

  return (
    <AuthPageShell>
      {status === 'loading' && (
        <>
          <CircularProgress />
          <Typography variant="body1">{message}</Typography>
        </>
      )}

      {status === 'error' && (
        <>
          <ErrorOutlineIcon sx={{ fontSize: rem(48), color: 'error.main' }} />
          <Typography sx={{ ...heading, textAlign: 'center' }}>
            Invitation could not be accepted
          </Typography>
          <Alert severity="error" sx={{ width: '100%' }}>
            {message}
          </Alert>
          <Typography variant="body2" color="text.secondary" align="center">
            The invitation may have expired or already been used. Ask an
            organization member to send a new one.
          </Typography>
          <Button
            variant="contained"
            href="/"
            fullWidth
            sx={{ ...primaryButton, mt: 1 }}
          >
            Back to sign in
          </Button>
        </>
      )}
    </AuthPageShell>
  );
}
