'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import InsightsPage from './components/InsightsPage';

/** The Insights dashboard itself, drawn as placeholders until its data arrives. */
export default function InsightsLoading() {
  return (
    <SkeletonMode>
      <InsightsPage />
    </SkeletonMode>
  );
}
