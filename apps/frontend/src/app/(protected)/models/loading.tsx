'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ModelsPageClient from './components/ModelsPageClient';

/** The Models page itself, drawn as placeholders until its data arrives. */
export default function ModelsLoading() {
  return (
    <SkeletonMode>
      <ModelsPageClient />
    </SkeletonMode>
  );
}
