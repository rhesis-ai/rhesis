'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import KnowledgeClientWrapper from '@/app/(protected)/knowledge/components/KnowledgeClientWrapper';

/** The Knowledge page itself, drawn as placeholders until its data arrives. */
export default function KnowledgeLoading() {
  return (
    <SkeletonMode>
      <KnowledgeClientWrapper />
    </SkeletonMode>
  );
}
