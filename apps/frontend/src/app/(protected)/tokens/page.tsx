import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';
import { Box, Typography } from '@mui/material';
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
    <PageContainer title="API Tokens" breadcrumbs={[]}>
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Create API tokens to authenticate with the Rhesis SDK and
          programmatically manage your testing workflows from your code.
        </Typography>
      </Box>
      <TokensPageClient sessionToken={session.session_token} />
    </PageContainer>
  );
}
