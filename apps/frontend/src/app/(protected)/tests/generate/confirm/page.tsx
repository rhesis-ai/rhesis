import { Box } from '@mui/material';
import { auth } from '@/auth';
import ConfirmTestGeneration from './components/ConfirmTestGeneration';

export default async function ConfirmTestGenerationPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 0 }}>
      <ConfirmTestGeneration sessionToken={session.session_token} />
    </Box>
  );
}
