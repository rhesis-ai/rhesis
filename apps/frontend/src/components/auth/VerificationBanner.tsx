'use client';

import { useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  CircularProgress,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import EmailIcon from '@mui/icons-material/EmailOutlined';
import { useSession } from 'next-auth/react';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function VerificationBanner() {
  const theme = useTheme();
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
        minHeight: 32,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <EmailIcon sx={{ fontSize: 16, color: textColor }} />
        <Typography
          variant="body2"
          sx={{
            color: textColor,
            fontWeight: 500,
            fontSize: '13px',
          }}
        >
          {resent
            ? 'Verification email sent! Check your inbox.'
            : 'Please verify your email address. Check your inbox for a verification link.'}
        </Typography>
        {!resent && (
          <Button
            size="small"
            onClick={handleResend}
            disabled={resending}
            startIcon={
              resending ? (
                <CircularProgress
                  size={12}
                  sx={{ color: textColor }}
                />
              ) : undefined
            }
            sx={{
              color: textColor,
              fontWeight: 600,
              fontSize: '12px',
              textTransform: 'none',
              minWidth: 'auto',
              py: 0,
              px: 1,
              ml: 0.5,
              borderRadius: 1,
              border: `1px solid ${alpha(textColor, 0.5)}`,
              '&:hover': {
                backgroundColor: alpha(textColor, 0.15),
                borderColor: textColor,
              },
            }}
          >
            Resend
          </Button>
        )}
      </Box>
      <IconButton
        size="small"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss banner"
        sx={{
          position: 'absolute',
          right: 8,
          color: textColor,
          opacity: 0.8,
          p: 0.25,
          '&:hover': {
            opacity: 1,
            backgroundColor: alpha(textColor, 0.1),
          },
        }}
      >
        <CloseIcon sx={{ fontSize: 16 }} />
      </IconButton>
    </Box>
  );
}
