'use client';

import { Alert, Button, Typography } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useSearchParams } from 'next/navigation';
import AuthPageShell from '@/components/auth/AuthPageShell';
import { useAuthStyles } from '@/components/auth/useAuthStyles';
import { rem } from '@/styles/theme-constants';

const ASK_ADMIN = 'Ask your administrator for help.';
const IF_IT_PERSISTS =
  'Try again, and tell your administrator if it keeps happening.';

/** One message per public code the backend sends (`ee/sso/login_errors.py`). */
const MESSAGES: Record<string, string> = {
  idp_denied: `Your identity provider didn’t finish the sign-in. If you cancelled it, start again. Otherwise, check with your administrator that you’re allowed to use Rhesis.`,
  expired:
    'This sign-in is no longer valid. It may have taken too long or been started in another tab. Start the sign-in again.',
  sso_unavailable: `Single sign-on isn’t available for this organization. Sign in another way, or ${ASK_ADMIN.toLowerCase()}`,
  idp_unreachable: `Rhesis couldn’t reach your organization’s identity provider. ${IF_IT_PERSISTS}`,
  idp_response_invalid: `Rhesis couldn’t verify the answer from your identity provider. ${IF_IT_PERSISTS}`,
  email_missing: `Your identity provider didn’t send a usable email address. ${ASK_ADMIN}`,
  email_unverified:
    'Your email address isn’t verified with your identity provider. Verify it there, then sign in again.',
  domain_not_allowed: `Your email domain can’t be used to sign in to this organization. ${ASK_ADMIN}`,
  account_elsewhere: `Your email address already belongs to another Rhesis organization. ${ASK_ADMIN}`,
  not_invited:
    'You don’t have an account in this organization yet. Ask your administrator to invite you.',
  no_seats:
    'This organization has no free seats. Ask your administrator to free one up.',
  no_access:
    'Your account isn’t in a group that has access to this organization. Ask your administrator to add you to one.',
  groups_unavailable: `Your groups couldn’t be read from your identity provider. ${IF_IT_PERSISTS}`,
};
const GENERIC = `Something went wrong while signing you in. ${IF_IT_PERSISTS}`;

export default function SSOErrorPage() {
  const { heading, primaryButton } = useAuthStyles();
  const params = useSearchParams();
  const code = params.get('error') ?? '';
  const ref = params.get('ref');
  const message = Object.hasOwn(MESSAGES, code) ? MESSAGES[code] : GENERIC;

  return (
    <AuthPageShell>
      <ErrorOutlineIcon sx={{ fontSize: rem(48), color: 'error.main' }} />
      <Typography component="h1" sx={{ ...heading, textAlign: 'center' }}>
        Couldn’t sign you in
      </Typography>
      <Alert severity="error" sx={{ width: '100%' }}>
        {message}
      </Alert>
      {ref && (
        <Typography variant="body2" color="text.secondary" align="center">
          Reference for your administrator: <code>{ref}</code>
        </Typography>
      )}
      <Button
        variant="contained"
        href="/"
        fullWidth
        sx={{ ...primaryButton, mt: 1 }}
      >
        Back to sign in
      </Button>
    </AuthPageShell>
  );
}
