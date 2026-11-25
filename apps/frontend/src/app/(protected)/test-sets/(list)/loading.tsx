'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TestSetsPageClient from '@/app/(protected)/test-sets/components/TestSetsPageClient';

/** The Test Sets page itself, drawn as placeholders until its data arrives. */
export default function TestSetsLoading() {
  return (
    <SkeletonMode>
      <TestSetsPageClient />
    </SkeletonMode>
  );
}
