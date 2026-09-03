'use client';

import React, { useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { SectionCard } from '@/components/common/SectionCard';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import ChangePasswordDrawer from './ChangePasswordDrawer';

interface SecuritySectionProps {
  userSettings?: UserSettings;
}

function formatProviderLabel(providerType?: string): string {
  const labels: Record<string, string> = {
    google: 'Google',
    github: 'GitHub',
    oidc: 'SSO',
    microsoft: 'Microsoft',
  };
  if (!providerType) return 'an external provider';
  return labels[providerType] ?? providerType;
}

export default function SecuritySection({
  userSettings,
}: SecuritySectionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);

  const hasPassword = userSettings?.has_password ?? false;
  const providerType = userSettings?.provider_type;

  return (
    <>
      <SectionCard title="Password">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography
            variant="body2"
            sx={{ color: theme => theme.palette.greyscale.body }}
          >
            {hasPassword
              ? 'Change your password. You will need to enter your current password.'
              : `You signed in with ${formatProviderLabel(providerType)}. You can set a password to also sign in with email.`}
          </Typography>

          <Box>
            <Button
              variant="outlined"
              startIcon={<LockOutlinedIcon />}
              onClick={() => setDialogOpen(true)}
            >
              {hasPassword ? 'Change Password' : 'Set Password'}
            </Button>
          </Box>
        </Box>
      </SectionCard>

      <ChangePasswordDrawer
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        hasPassword={hasPassword}
      />
    </>
  );
}
