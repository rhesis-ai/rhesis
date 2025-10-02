import { Box } from '@mui/material';
import { auth } from '@/auth';
import TestGenerationLanding from './components/TestGenerationLanding';

export default async function TestGenerationPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 0 }}>
      <TestGenerationLanding sessionToken={session.session_token} />
    </Box>
  );
}
