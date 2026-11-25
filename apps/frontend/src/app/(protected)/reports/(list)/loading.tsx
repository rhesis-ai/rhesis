'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ReportsPageClient from '@/app/(protected)/reports/components/ReportsPageClient';

/** The Reports page itself, drawn as placeholders until its data arrives. */
export default function ReportsLoading() {
  return (
    <SkeletonMode>
      <ReportsPageClient />
    </SkeletonMode>
  );
}
