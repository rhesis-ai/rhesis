import { Box } from '@mui/material';
import { auth } from '@/auth';
import GenerateTestsStepper from './components/GenerateTestsStepper';

export default async function GenerateTestsPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 0 }}>
      <GenerateTestsStepper sessionToken={session.session_token} />
    </Box>
  );
}
