'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TracesClientWrapper from '../components/TracesClientWrapper';

/** The Traces page itself, drawn as placeholders until its data arrives. */
export default function TracesLoading() {
  return (
    <SkeletonMode>
      <TracesClientWrapper />
    </SkeletonMode>
  );
}
