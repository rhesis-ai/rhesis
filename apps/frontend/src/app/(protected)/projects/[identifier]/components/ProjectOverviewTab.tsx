'use client';

import * as React from 'react';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectMetadataCard from './ProjectMetadataCard';
import ProjectTagsCard from './ProjectTagsCard';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface ProjectOverviewTabProps {
  project: Project;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectOverviewTab({
  project,
  onProjectUpdate,
}: ProjectOverviewTabProps) {
  const canUpdateProject = useCan(Capability.Project.UPDATE);

  return (
    <>
      <ProjectMetadataCard
        project={project}
        onSave={onProjectUpdate}
        editable={canUpdateProject}
      />

      <ProjectTagsCard
        project={project}
        onSave={onProjectUpdate}
        editable={canUpdateProject}
      />
    </>
  );
}
