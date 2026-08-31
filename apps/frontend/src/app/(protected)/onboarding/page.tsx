import OnboardingPageClient from './components/OnboardingPageClient';
import { getOnboardingVideoUrl } from '@/utils/onboarding-video';
import { UUID } from 'crypto';
import { requireSession } from '@/utils/require-session';

export const dynamic = 'force-dynamic';

export default async function OnboardingPage() {
  const session = await requireSession();

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
