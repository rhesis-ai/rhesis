import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';
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
    <PageContainer
      title="API Tokens"
      breadcrumbs={[{ title: 'API Tokens', path: '/tokens' }]}
    >
      <TokensPageClient sessionToken={session.session_token} />
    </PageContainer>
  );
}
