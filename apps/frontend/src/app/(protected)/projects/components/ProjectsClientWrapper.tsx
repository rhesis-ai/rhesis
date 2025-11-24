'use client';

import React, { useState, useEffect } from 'react';
import { Box, Typography, Grid, Button, Alert, Paper } from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectCard from './ProjectCard';
import AddIcon from '@mui/icons-material/Add';
import FolderIcon from '@mui/icons-material/Folder';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import Link from 'next/link';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import styles from '@/styles/ProjectsClientWrapper.module.css';

/** Type for alert/snackbar severity */
type AlertSeverity = 'success' | 'error' | 'info' | 'warning';

/** Props for the EmptyStateMessage component */
interface EmptyStateMessageProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
}

/**
 * Reusable empty state component with customizable title, description and icon
 */
function EmptyStateMessage({
  title,
  description,
  icon,
}: EmptyStateMessageProps) {
  return (
    <Paper elevation={2} className={styles.emptyState}>
      {icon || (
        <Box className={styles.iconContainer}>
          <FolderIcon className={styles.primaryIcon} />
          <AutoAwesomeIcon className={styles.secondaryIcon} />
        </Box>
      )}

      <Typography variant="h5" className={styles.title}>
        {title}
      </Typography>

      <Typography variant="body1" className={styles.description}>
        {description}
      </Typography>
    </Paper>
  );
}

/** Props for the ProjectsClientWrapper component */
interface ProjectsClientWrapperProps {
  initialProjects: Project[];
  sessionToken: string;
}

/**
 * Client component for the Projects page
 * Handles displaying projects
 */
export default function ProjectsClientWrapper({
  initialProjects = [],
  sessionToken,
}: ProjectsClientWrapperProps) {
  const [projects, setProjects] = useState<Project[]>(initialProjects || []);
  const notifications = useNotifications();
  const { markStepComplete, progress, isComplete, activeTour } =
    useOnboarding();

  // Check if user is currently on the project tour
  const isOnProjectTour = activeTour === 'project';

  // Disable button ONLY when user is actively on a tour OTHER than project
  const isProjectButtonDisabled = activeTour !== null && !isOnProjectTour;

  // Enable tour for this page
  useOnboardingTour('project');

  // Mark step as complete when user has projects
  useEffect(() => {
    if (projects.length > 0 && !progress.projectCreated) {
      markStepComplete('projectCreated');
    }
  }, [projects.length, progress.projectCreated, markStepComplete]);

  // Show error state if no session token
  if (!sessionToken) {
    return (
      <PageContainer
        title="Projects"
        breadcrumbs={[{ title: 'Projects', path: '/projects' }]}
      >
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EmptyStateMessage
          title="Authentication Required"
          description="Please log in to view and manage your projects."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Projects"
      breadcrumbs={[{ title: 'Projects', path: '/projects' }]}
    >
      {/* Header with actions */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Button
          component={isProjectButtonDisabled ? 'button' : Link}
          href={isProjectButtonDisabled ? undefined : '/projects/create-new'}
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          data-tour="create-project-button"
          disabled={isProjectButtonDisabled}
        >
          Create Project
        </Button>
      </Box>

      {/* Projects grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {Array.isArray(projects) &&
          projects.map(project => (
            <Grid item key={project.id} xs={12} md={6} lg={4}>
              <ProjectCard project={project} />
            </Grid>
          ))}

        {(!Array.isArray(projects) || projects.length === 0) && (
          <Grid item xs={12}>
            <EmptyStateMessage
              title="No projects found"
              description="Create your first project to start building and testing your AI applications. Projects help you organize your work and collaborate with your team."
            />
          </Grid>
        )}
      </Grid>
    </PageContainer>
  );
}
