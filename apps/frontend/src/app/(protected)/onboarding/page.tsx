import { auth } from '@/auth';
import OnboardingPageClient from './components/OnboardingPageClient';
import { UUID } from 'crypto';

export default async function OnboardingPage() {
  const session = await auth();
  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  if (!session?.user?.id) {
    throw new Error('No user ID available in session');
  }

  return (
    <OnboardingPageClient
      sessionToken={session.session_token}
      userId={session.user.id as UUID}
    />
  );
}
