'use client';

import { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  CircularProgress,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import EmailIcon from '@mui/icons-material/EmailOutlined';
import { useSession } from 'next-auth/react';
import { getBaseUrl } from '@/utils/url-resolver';

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** What to tell the user, given when their account locks (if it does). */
export function verificationMessage(
  dueAt: string | null | undefined,
  now: number = Date.now()
): string {
  const due = dueAt ? Date.parse(dueAt) : NaN;
  if (Number.isNaN(due)) {
    return 'Please verify your email address. Check your inbox for a verification link.';
  }
  const daysLeft = Math.ceil((due - now) / MS_PER_DAY);
  if (daysLeft <= 1) {
    return 'Verify your email today to keep access to your account. Check your inbox for the link.';
  }
  return `Verify your email within ${daysLeft} days to keep access to your account. Check your inbox for the link.`;
}

export default function VerificationBanner() {
  const theme = useTheme();
  const { data: session } = useSession();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const user = session?.user;
  const isEmailVerified = user?.is_email_verified ?? true;

  // Not dismissible: the account locks if the address isn't verified in time.
  if (isEmailVerified || !user?.email) {
    return null;
  }

  const handleResend = async () => {
    setResending(true);
    try {
      await fetch(`${getBaseUrl()}/auth/resend-verification`, {
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

  const isDark = theme.palette.mode === 'dark';
  const bgGradient = isDark
    ? `linear-gradient(135deg, ${alpha(theme.palette.info.dark, 0.85)} 0%, ${alpha(theme.palette.info.main, 0.7)} 100%)`
    : `linear-gradient(135deg, ${theme.palette.warning.main} 0%, ${theme.palette.warning.light} 100%)`;
  const textColor = isDark
    ? theme.palette.info.contrastText
    : theme.palette.warning.contrastText;

  return (
    <Box
      sx={{
        background: bgGradient,
        py: 0.5,
        px: 2,
        minHeight: theme => theme.spacing(4),
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <EmailIcon
          sx={{
            fontSize: theme => theme.typography.body2.fontSize,
            color: textColor,
          }}
        />
        <Typography
          variant="caption"
          sx={{
            color: textColor,
            fontWeight: theme => theme.typography.fontWeightMedium,
          }}
        >
          {resent
            ? 'Verification email sent! Check your inbox.'
            : verificationMessage(user.email_verification_due_at)}
        </Typography>
        {!resent && (
          <Button
            size="small"
            color="inherit"
            onClick={handleResend}
            disabled={resending}
            startIcon={
              resending ? (
                <CircularProgress size="1em" sx={{ color: textColor }} />
              ) : undefined
            }
            sx={{
              color: textColor,
              fontWeight: theme => theme.typography.fontWeightBold,
              fontSize: theme => theme.typography.caption.fontSize,
              textTransform: 'none',
              minWidth: 'auto',
              py: 0,
              px: 1,
              ml: 0.5,
              borderRadius: theme => `${theme.shape.borderRadius}px`,
              border: `1px solid ${alpha(textColor, 0.5)}`,
              '&:hover': {
                backgroundColor: alpha(textColor, 0.15),
                borderColor: textColor,
              },
              '&.Mui-disabled': {
                color: textColor,
                borderColor: alpha(textColor, 0.5),
                opacity: theme => theme.palette.action.disabledOpacity,
              },
            }}
          >
            Resend
          </Button>
        )}
      </Box>
    </Box>
  );
}
