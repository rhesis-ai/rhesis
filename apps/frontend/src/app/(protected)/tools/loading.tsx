'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ToolsPageClient from './components/ToolsPageClient';

/** The Tools page itself, drawn as placeholders until its data arrives. */
export default function ToolsLoading() {
  return (
    <SkeletonMode>
      <ToolsPageClient />
    </SkeletonMode>
  );
}
