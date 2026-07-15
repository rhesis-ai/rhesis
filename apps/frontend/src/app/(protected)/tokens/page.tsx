import { Metadata } from 'next';
import { Alert, Paper } from '@mui/material';
import { auth } from '@/auth';
import TokensPageClient from './components/TokensPageClient';

export const metadata: Metadata = {
  title: 'API Tokens',
};

export default async function TokensPage() {
  const session = await auth();

  if (!session || session.error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          Authentication required. Please sign in to view API tokens.
        </Alert>
      </Paper>
    );
  }

  return <TokensPageClient sessionToken={session.session_token ?? ''} />;
}
