'use client';

import * as React from 'react';
import { useRef } from 'react';
import { Alert, Button } from '@mui/material';
import { AddIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { ProjectEnvironmentsData } from './project-data';
import ProjectParameters from './ProjectParameters';
import ProjectEnvironments, {
  type ProjectEnvironmentsHandle,
} from './ProjectEnvironments';

const EXPERIMENTS_ALERT =
  'Parameters and environments configure how this project resolves ' +
  'experiment versions at runtime.';

interface ProjectExperimentsTabProps {
  projectId: string;
  initialEnvironments?: ProjectEnvironmentsData;
}

export default function ProjectExperimentsTab({
  projectId,
  initialEnvironments,
}: ProjectExperimentsTabProps) {
  const canUpdateProject = useCan(Capability.Project.UPDATE);
  const environmentsRef = useRef<ProjectEnvironmentsHandle>(null);

  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        {EXPERIMENTS_ALERT}
      </Alert>

      <ProjectParameters projectId={projectId} embedInSectionCard />

      <SectionCard
        title="Environments"
        actions={
          canUpdateProject ? (
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon sx={{ fontSize: 20 }} />}
              onClick={() => environmentsRef.current?.openAddDrawer()}
              sx={sectionEditButtonSx}
            >
              New Environment
            </Button>
          ) : undefined
        }
      >
        <ProjectEnvironments
          ref={environmentsRef}
          projectId={projectId}
          hideToolbarAddButton
          initialData={initialEnvironments}
        />
      </SectionCard>
    </>
  );
}
