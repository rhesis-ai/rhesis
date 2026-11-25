import OnboardingPageClient from './components/OnboardingPageClient';
import {
  getOnboardingVideoEmbedUrl,
  getOnboardingVideoUrl,
} from '@/utils/onboarding-video';
import { UUID } from 'crypto';
import { requireSession } from '@/utils/require-session';

export const dynamic = 'force-dynamic';

export default async function OnboardingPage() {
  const session = await requireSession();

  if (!session?.user?.id) {
    throw new Error('No user ID available in session');
  }

  // Resolved at request time from pod env (Helm ConfigMap), not client bundle.
  // Without a playable video the welcome step is left out.
  const rawVideoUrl = getOnboardingVideoUrl();
  const videoUrl =
    rawVideoUrl && getOnboardingVideoEmbedUrl(rawVideoUrl)
      ? rawVideoUrl
      : undefined;

  return (
    <OnboardingPageClient
      userId={session.user.id as UUID}
      videoUrl={videoUrl}
    />
  );
}
