'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import TasksPageClient from '@/app/(protected)/tasks/components/TasksPageClient';

/** The Tasks page itself, drawn as placeholders until its data arrives. */
export default function TasksLoading() {
  return (
    <SkeletonMode>
      <TasksPageClient />
    </SkeletonMode>
  );
}
