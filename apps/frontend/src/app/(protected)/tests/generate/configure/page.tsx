import { Box } from '@mui/material';
import { auth } from '@/auth';
import TestConfiguration from './components/TestConfiguration';

export default async function TestConfigurationPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 0 }}>
      <TestConfiguration sessionToken={session.session_token} />
    </Box>
  );
}
