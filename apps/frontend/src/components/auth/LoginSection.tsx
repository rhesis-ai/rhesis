'use client';

import { Box } from '@mui/material';
import AuthForm from './AuthForm';

interface LoginSectionProps {
  /** If true, show registration form instead of login */
  isRegistration?: boolean;
}

export default function LoginSection({
  isRegistration = false,
}: LoginSectionProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        width: '100%',
      }}
    >
      <Box sx={{ width: '100%' }}>
        <AuthForm isRegistration={isRegistration} />
      </Box>
    </Box>
  );
}
