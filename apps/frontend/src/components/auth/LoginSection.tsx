'use client';

import { Box } from '@mui/material';
import CustomAuthForm from './Auth0Lock';

export default function LoginSection() {
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
        <CustomAuthForm
          clientId={process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID!}
          domain={process.env.NEXT_PUBLIC_AUTH0_DOMAIN!}
        />
      </Box>
    </Box>
  );
}
