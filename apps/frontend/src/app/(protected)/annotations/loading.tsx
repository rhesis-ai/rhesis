'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import AnnotationsPageClient from '@/app/(protected)/annotations/components/AnnotationsPageClient';

/** The Annotations page itself, drawn as placeholders until its data arrives. */
export default function AnnotationsLoading() {
  return (
    <SkeletonMode>
      <AnnotationsPageClient />
    </SkeletonMode>
  );
}
