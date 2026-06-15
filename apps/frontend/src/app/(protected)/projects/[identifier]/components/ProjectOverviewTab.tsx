'use client';

import * as React from 'react';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectMetadataCard from './ProjectMetadataCard';
import ProjectTagsCard from './ProjectTagsCard';

interface ProjectOverviewTabProps {
  project: Project;
  sessionToken: string;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectOverviewTab({
  project,
  sessionToken,
  onProjectUpdate,
}: ProjectOverviewTabProps) {
  return (
    <>
      <ProjectMetadataCard
        project={project}
        sessionToken={sessionToken}
        onSave={onProjectUpdate}
      />

      <ProjectTagsCard project={project} onSave={onProjectUpdate} />
    </>
  );
}
