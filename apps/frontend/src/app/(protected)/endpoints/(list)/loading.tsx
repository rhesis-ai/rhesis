'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import EndpointsPageClient from '@/app/(protected)/endpoints/components/EndpointsPageClient';

/** The Endpoints page itself, drawn as placeholders until its data arrives. */
export default function EndpointsLoading() {
  return (
    <SkeletonMode>
      <EndpointsPageClient />
    </SkeletonMode>
  );
}
