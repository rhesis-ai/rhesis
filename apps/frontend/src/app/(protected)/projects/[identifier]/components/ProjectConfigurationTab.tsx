'use client';

import * as React from 'react';
import { useRef } from 'react';
import { Alert, Button } from '@mui/material';
import { AddIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { Project } from '@/utils/api-client/interfaces/project';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
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
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectConfigurationTab({
  project,
  projectId,
  onProjectUpdate,
}: ProjectConfigurationTabProps) {
  const canUpdateProject = useCan(Capability.Project.UPDATE);
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
          canUpdateProject ? (
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon sx={{ fontSize: 20 }} />}
              onClick={() => traceMetricsRef.current?.openAddDialog()}
              sx={sectionEditButtonSx}
            >
              Add Metric
            </Button>
          ) : undefined
        }
      >
        <ProjectTraceMetrics
          ref={traceMetricsRef}
          project={project}
          onProjectUpdate={onProjectUpdate}
        />
      </SectionCard>

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
        />
      </SectionCard>
    </>
  );
}
