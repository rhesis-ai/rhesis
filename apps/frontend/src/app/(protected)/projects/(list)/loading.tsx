'use client';

import { SkeletonMode } from '@/components/loading/SkeletonMode';
import ProjectsClientWrapper from '../components/ProjectsClientWrapper';

/** The Projects page itself, drawn as placeholders until its data arrives. */
export default function ProjectsLoading() {
  return (
    <SkeletonMode>
      <ProjectsClientWrapper />
    </SkeletonMode>
  );
}
