'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TestsPageClient from '../components/TestsPageClient';

/** The Tests page itself, drawn as placeholders until its data arrives. */
export default function TestsLoading() {
  return (
    <SkeletonMode>
      <TestsPageClient />
    </SkeletonMode>
  );
}
