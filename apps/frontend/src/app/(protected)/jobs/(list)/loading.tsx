'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import JobsPageClient from '@/app/(protected)/jobs/components/JobsPageClient';

/** The Jobs page itself, drawn as placeholders until its data arrives. */
export default function JobsLoading() {
  return (
    <SkeletonMode>
      <JobsPageClient />
    </SkeletonMode>
  );
}
