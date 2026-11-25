'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TestRunsPageClient from '@/app/(protected)/test-runs/components/TestRunsPageClient';

/** The Test Runs page itself, drawn as placeholders until its data arrives. */
export default function TestRunsLoading() {
  return (
    <SkeletonMode>
      <TestRunsPageClient />
    </SkeletonMode>
  );
}
