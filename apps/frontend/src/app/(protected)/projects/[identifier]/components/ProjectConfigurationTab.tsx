'use client';

import * as React from 'react';
import { useRef } from 'react';
import { Alert, Button } from '@mui/material';
import { AddIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectTraceMetrics, {
  type ProjectTraceMetricsHandle,
} from './ProjectTraceMetrics';
import ProjectParameters from './ProjectParameters';
import ProjectEnvironments, {
  type ProjectEnvironmentsHandle,
} from './ProjectEnvironments';

const CONFIGURATION_ALERT =
  'Trace metrics, parameters, and environments configure how this project ' +
  'evaluates traces and resolves experiment versions at runtime.';

interface ProjectConfigurationTabProps {
  project: Project;
  projectId: string;
  sessionToken: string;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectConfigurationTab({
  project,
  projectId,
  sessionToken,
  onProjectUpdate,
}: ProjectConfigurationTabProps) {
  const traceMetricsRef = useRef<ProjectTraceMetricsHandle>(null);
  const environmentsRef = useRef<ProjectEnvironmentsHandle>(null);

  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        {CONFIGURATION_ALERT}
      </Alert>

      <SectionCard
        title="Trace Metrics"
        actions={
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon sx={{ fontSize: 20 }} />}
            onClick={() => traceMetricsRef.current?.openAddDialog()}
            sx={sectionEditButtonSx}
          >
            Add Metric
          </Button>
        }
      >
        <ProjectTraceMetrics
          ref={traceMetricsRef}
          project={project}
          sessionToken={sessionToken}
          onProjectUpdate={onProjectUpdate}
        />
      </SectionCard>

      <ProjectParameters
        projectId={projectId}
        sessionToken={sessionToken}
        embedInSectionCard
      />

      <SectionCard
        title="Environments"
        actions={
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon sx={{ fontSize: 20 }} />}
            onClick={() => environmentsRef.current?.openAddDrawer()}
            sx={sectionEditButtonSx}
          >
            New Environment
          </Button>
        }
      >
        <ProjectEnvironments
          ref={environmentsRef}
          projectId={projectId}
          sessionToken={sessionToken}
          hideToolbarAddButton
        />
      </SectionCard>
    </>
  );
}
