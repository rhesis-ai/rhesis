'use client';

import { useState, useCallback } from 'react';
import { Box, Button, Paper, Tab, Tabs, Typography } from '@mui/material';
import { EditIcon, DeleteIcon } from '@/components/icons';
import ProjectContent from '../components/ProjectContent';
import ProjectEditDrawer from './edit-drawer';
import ProjectEndpoints from './components/ProjectEndpoints';
import ProjectTraceMetrics from './components/ProjectTraceMetrics';
import ProjectParameters from './components/ProjectParameters';
import ProjectEnvironments from './components/ProjectEnvironments';
import { Project } from '@/utils/api-client/interfaces/project';
import { BuiltInEnvironment } from '@/utils/api-client/interfaces/parameters';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import {
  PageLayout,
  type BreadcrumbItem,
} from '@/components/layout/PageLayout';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
interface ClientWrapperProps {
  project: Project;
  sessionToken: string;
  projectId: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`project-tabpanel-${index}`}
      aria-labelledby={`project-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const PROJECT_TABS = [
  {
    label: 'Endpoints',
    description:
      'Endpoints are the HTTP targets Rhesis calls when running tests against this project. Add an endpoint to point Rhesis at your application.',
  },
  {
    label: 'Trace Metrics',
    description:
      'Trace metrics evaluate every trace produced by this project. They run automatically in the background as new traces arrive.',
  },
  {
    label: 'Parameters',
    description:
      'Parameters define the typed schema your tests and experiments accept. Each field becomes a named input with a type, default value, and validation rules.',
  },
  {
    label: 'Environments',
    description:
      `Environments are movable pointers at one (experiment, version) pair. ` +
      `SDK consumers and test runs that ask for an environment resolve to ` +
      `whatever it points at. The well-known names below — ` +
      `${BuiltInEnvironment.ALL.join(', ')} — render even when no ` +
      `experiment is promoted.`,
  },
] as const;

const PROJECT_TAB_QUERY_VALUES: Record<string, number> = {
  endpoints: 0,
  traceMetrics: 1,
  parameters: 2,
  environments: 3,
};

export default function ClientWrapper({
  project,
  sessionToken,
  projectId,
}: ClientWrapperProps) {
  const router = useRouter();
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const tourId = searchParams.get('tour');
  useOnboardingTour(tourId === 'endpoint' ? 'endpoint' : undefined);
  const tabParam = searchParams.get('tab');
  const initialTab =
    tabParam && tabParam in PROJECT_TAB_QUERY_VALUES
      ? PROJECT_TAB_QUERY_VALUES[tabParam]
      : 0;
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(project);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [currentTab, setCurrentTab] = useState(initialTab);
  const notifications = useNotifications();

  const title = currentProject.name || `Project ${params.identifier}`;
  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Projects', href: '/projects' },
    { label: title },
  ];

  const handleUpdateProject = useCallback(
    async (updatedProject: Partial<Project>) => {
      setIsUpdating(true);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const projectsClient = apiFactory.getProjectsClient();
        const response = await projectsClient.updateProject(
          projectId,
          updatedProject
        );

        // Preserve the owner object from currentProject if response doesn't include it
        const updatedProjectWithOwner = {
          ...response,
          owner: response.owner || currentProject.owner,
          owner_id: response.owner_id || currentProject.owner_id,
        };

        setCurrentProject(updatedProjectWithOwner);
        setIsDrawerOpen(false);
        notifications.show('Project updated successfully', {
          severity: 'success',
        });
      } catch (error) {
        notifications.show(
          error instanceof Error ? error.message : 'Failed to update project',
          { severity: 'error' }
        );
      } finally {
        setIsUpdating(false);
      }
    },
    [projectId, sessionToken, notifications, currentProject]
  );

  const handleDeleteClick = () => {
    setDeleteConfirmOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const projectsClient = apiFactory.getProjectsClient();
      await projectsClient.deleteProject(projectId);
      notifications.show('Project deleted successfully', {
        severity: 'success',
      });
      router.push('/projects');
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to delete project',
        { severity: 'error' }
      );
      setDeleteConfirmOpen(false);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <PageLayout title={title} breadcrumbs={breadcrumbs}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Button
          variant="contained"
          startIcon={<EditIcon />}
          onClick={() => setIsDrawerOpen(true)}
          disabled={isUpdating || isDeleting}
          sx={{ mr: 2 }}
        >
          Edit Project
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={handleDeleteClick}
          disabled={isUpdating || isDeleting}
        >
          Delete
        </Button>
      </Box>

      {/* Project Overview */}
      <ProjectContent project={currentProject} />

      {/* Tabbed sections */}
      <Paper variant="outlined" sx={{ mt: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={currentTab}
            onChange={(_e, value) => setCurrentTab(value)}
            aria-label="project sections"
          >
            {PROJECT_TABS.map(tab => (
              <Tab key={tab.label} label={tab.label} />
            ))}
          </Tabs>
        </Box>

        <TabPanel value={currentTab} index={0}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {PROJECT_TABS[0].description}
          </Typography>
          <ProjectEndpoints projectId={projectId} sessionToken={sessionToken} />
        </TabPanel>

        <TabPanel value={currentTab} index={1}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {PROJECT_TABS[1].description}
          </Typography>
          <ProjectTraceMetrics
            project={currentProject}
            sessionToken={sessionToken}
            onProjectUpdate={handleUpdateProject}
          />
        </TabPanel>

        <TabPanel value={currentTab} index={2}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {PROJECT_TABS[2].description}
          </Typography>
          <ProjectParameters
            projectId={projectId}
            sessionToken={sessionToken}
            title="Define schema"
          />
        </TabPanel>

        <TabPanel value={currentTab} index={3}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {PROJECT_TABS[3].description}
          </Typography>
          <ProjectEnvironments
            projectId={projectId}
            sessionToken={sessionToken}
          />
        </TabPanel>
      </Paper>

      {/* Edit Drawer */}
      <ProjectEditDrawer
        project={currentProject}
        sessionToken={sessionToken}
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSave={handleUpdateProject}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteModal
        open={deleteConfirmOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        itemType="project"
        itemName={currentProject.name}
        title="Delete Project"
      />
    </PageLayout>
  );
}
