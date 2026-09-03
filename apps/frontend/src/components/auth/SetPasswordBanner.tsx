'use client';

import { useState } from 'react';
import { Box, Button, IconButton, Typography, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useRouter } from 'next/navigation';
import { useUserSettings } from '@/hooks/useUserSettings';

export default function SetPasswordBanner() {
  const theme = useTheme();
  const router = useRouter();
  const { data: settings, isLoading } = useUserSettings();
  const [dismissed, setDismissed] = useState(false);

  if (isLoading || dismissed || !settings) return null;

  // Show when the user has no password and no external auth provider.
  // provider_type is null for invited users and "email" for email-signup
  // users; any other value means they have an OAuth/SSO provider and
  // can sign in without a password.
  const provider = settings.provider_type;
  const hasExternalProvider = !!provider && provider !== 'email';
  if (settings.has_password || hasExternalProvider) return null;

  const isDark = theme.palette.mode === 'dark';
  const bgGradient = isDark
    ? `linear-gradient(135deg, ${alpha(theme.palette.info.dark, 0.85)} 0%, ${alpha(theme.palette.info.main, 0.7)} 100%)`
    : `linear-gradient(135deg, ${theme.palette.info.main} 0%, ${theme.palette.info.light} 100%)`;
  const textColor = isDark
    ? theme.palette.info.contrastText
    : theme.palette.info.contrastText;

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
        position: 'relative',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <LockOutlinedIcon
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
          Set a password so you can sign in anytime.
        </Typography>
        <Button
          size="small"
          color="inherit"
          onClick={() => router.push('/settings?tab=security')}
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
          }}
        >
          Set Password
        </Button>
      </Box>
      <IconButton
        size="small"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss banner"
        sx={{
          position: 'absolute',
          right: theme => theme.spacing(1),
          color: textColor,
          opacity: 0.8,
          p: 0.25,
          '&:hover': {
            opacity: 1,
            backgroundColor: alpha(textColor, 0.1),
          },
        }}
      >
        <CloseIcon sx={{ fontSize: theme => theme.typography.body2.fontSize }} />
      </IconButton>
    </Box>
  );
}
