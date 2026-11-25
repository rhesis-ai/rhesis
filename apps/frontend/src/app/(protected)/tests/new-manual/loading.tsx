'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ManualTestWriter, {
  type ManualTestWriterInitialData,
} from './components/ManualTestWriter';

// Empty option lists: the writer skips its own fetch and draws its one blank
// row, which is what the page opens with.
const NO_OPTIONS: ManualTestWriterInitialData = {
  requirements: [],
  topics: [],
  categories: [],
};

/** The Manual Test Writer itself, inert, until its option lists arrive. */
export default function ManualTestWriterLoading() {
  return (
    <SkeletonMode>
      <ManualTestWriter initialData={NO_OPTIONS} />
    </SkeletonMode>
  );
}
