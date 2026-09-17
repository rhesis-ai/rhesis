'use client';

import * as React from 'react';
import { useRef } from 'react';
import { Alert, Button } from '@mui/material';
import { AddIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { Project } from '@/utils/api-client/interfaces/project';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import ProjectTraceMetrics, {
  type ProjectTraceMetricsHandle,
} from './ProjectTraceMetrics';

const TRACES_ALERT =
  'Trace metrics configure how this project evaluates traces.';

interface ProjectTracesTabProps {
  project: Project;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
  initialTraceMetrics?: MetricDetail[];
}

export default function ProjectTracesTab({
  project,
  onProjectUpdate,
  initialTraceMetrics,
}: ProjectTracesTabProps) {
  const canUpdateProject = useCan(Capability.Project.UPDATE);
  const traceMetricsRef = useRef<ProjectTraceMetricsHandle>(null);

  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        {TRACES_ALERT}
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
          initialMetrics={initialTraceMetrics}
        />
      </SectionCard>
    </>
  );
}
