'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TokensPageClient from '@/app/(protected)/tokens/components/TokensPageClient';

/** The API Tokens page itself, drawn as placeholders until its data arrives. */
export default function TokensLoading() {
  return (
    <SkeletonMode>
      <TokensPageClient />
    </SkeletonMode>
  );
}
