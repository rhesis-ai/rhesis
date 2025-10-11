import { Metadata } from 'next';
import { Box } from '@mui/material';
import { auth } from '@/auth';
import TokensPageClient from './components/TokensPageClient';

export const metadata: Metadata = {
  title: 'API Tokens',
};

export default async function TokensPage() {
  const session = await auth();
  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <Box sx={{ p: 3 }}>
      <TokensPageClient sessionToken={session.session_token} />
    </Box>
  );
}
