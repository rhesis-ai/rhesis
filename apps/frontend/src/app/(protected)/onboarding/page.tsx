import { auth } from '@/auth';
import OnboardingPageClient from './components/OnboardingPageClient';
import { getOnboardingVideoUrl } from '@/utils/onboarding-video';
import { UUID } from 'crypto';

export const dynamic = 'force-dynamic';

export default async function OnboardingPage() {
  const session = await auth();
  if (!session || session.error) {
    throw new Error('No session token available');
  }

  if (!session?.user?.id) {
    throw new Error('No user ID available in session');
  }

  // Resolved at request time from pod env (Helm ConfigMap), not client bundle.
  const videoUrl = getOnboardingVideoUrl();

  return (
    <OnboardingPageClient
      userId={session.user.id as UUID}
      videoUrl={videoUrl}
    />
  );
}
