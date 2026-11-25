'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ExperimentsClientWrapper from '@/app/(protected)/experiments/components/ExperimentsClientWrapper';

/** The Experiments page itself, drawn as placeholders until its data arrives. */
export default function ExperimentsLoading() {
  return (
    <SkeletonMode>
      <ExperimentsClientWrapper />
    </SkeletonMode>
  );
}
