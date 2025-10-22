import { Box } from '@mui/material';
import { auth } from '@/auth';
import DescribeTestRequirements from './components/DescribeTestRequirements';

export default async function DescribeTestPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 0 }}>
      <DescribeTestRequirements sessionToken={session.session_token} />
    </Box>
  );
}
