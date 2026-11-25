'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TracesClientWrapper from '../components/TracesClientWrapper';

/** This route only looks the span up and redirects to the Traces page with
 *  its drawer open, so the wait shows the Traces page itself, as its own
 *  loading view does. */
export default function TraceDetailLoading() {
  return (
    <SkeletonMode>
      <TracesClientWrapper />
    </SkeletonMode>
  );
}
