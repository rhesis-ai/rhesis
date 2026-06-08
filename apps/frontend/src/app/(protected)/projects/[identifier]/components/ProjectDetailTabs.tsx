'use client';

import * as React from 'react';
import { useCallback } from 'react';
import { Alert, Box } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectOverviewTab from './ProjectOverviewTab';
import ProjectEndpoints from './ProjectEndpoints';
import ProjectConfigurationTab from './ProjectConfigurationTab';
import ProjectMembersTab from './ProjectMembersTab';

const TAB_KEYS = ['overview', 'members', 'endpoints', 'configuration'] as const;
type ProjectTabKey = (typeof TAB_KEYS)[number];

const TAB_LABELS: Record<ProjectTabKey, string> = {
  overview: 'Overview',
  members: 'Members',
  endpoints: 'Endpoints',
  configuration: 'Advanced Configuration',
};

const LEGACY_TAB_MAP: Record<string, ProjectTabKey> = {
  endpoints: 'endpoints',
  traceMetrics: 'configuration',
  parameters: 'configuration',
  environments: 'configuration',
  members: 'members',
};

const ENDPOINTS_ALERT =
  'Endpoints are the HTTP targets Rhesis calls when running tests against ' +
  'this project. Add an endpoint to point Rhesis at your application.';

function normalizeTabParam(param: string | null): ProjectTabKey {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && TAB_KEYS.includes(param as ProjectTabKey)) {
    return param as ProjectTabKey;
  }
  return 'overview';
}

interface ProjectDetailTabsProps {
  project: Project;
  projectId: string;
  sessionToken: string;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectDetailTabs({
  project,
  projectId,
  sessionToken,
  onProjectUpdate,
}: ProjectDetailTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = (() => {
    const key = normalizeTabParam(searchParams.get('tab'));
    return TAB_KEYS.indexOf(key);
  })();

  const handleTabChange = useCallback(
    (newIndex: number) => {
      const key = TAB_KEYS[newIndex];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
    id: `project-detail-tab-${index}`,
    'aria-controls': `project-detail-tabpanel-${index}`,
  }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Project detail sections"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="project-detail">
        <ProjectOverviewTab
          project={project}
          sessionToken={sessionToken}
          onProjectUpdate={onProjectUpdate}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="project-detail">
        <ProjectMembersTab
          project={project}
          projectId={projectId}
          sessionToken={sessionToken}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="project-detail">
        <Alert severity="info" sx={{ mb: 3 }}>
          {ENDPOINTS_ALERT}
        </Alert>
        <ProjectEndpoints projectId={projectId} sessionToken={sessionToken} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="project-detail">
        <ProjectConfigurationTab
          project={project}
          projectId={projectId}
          sessionToken={sessionToken}
          onProjectUpdate={onProjectUpdate}
        />
      </DetailTabPanel>
    </Box>
  );
}

/** Exported for tests and legacy URL handling documentation. */
export { TAB_KEYS, LEGACY_TAB_MAP };
