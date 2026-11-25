'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import PlaygroundClient from './components/PlaygroundClient';

/** The Playground itself, its chat panel empty until the page arrives. */
export default function PlaygroundLoading() {
  return (
    <SkeletonMode>
      <PlaygroundClient />
    </SkeletonMode>
  );
}
