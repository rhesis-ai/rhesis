'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Typography, Grid, Button, CircularProgress, Alert, Paper } from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectCard from './ProjectCard';
import AddIcon from '@mui/icons-material/Add';
import FolderIcon from '@mui/icons-material/Folder';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import Link from 'next/link';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import RefreshIcon from '@mui/icons-material/Refresh';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import { PaginatedResponse } from '@/utils/api-client/interfaces/common';

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
function EmptyStateMessage({ title, description, icon }: EmptyStateMessageProps) {
  return (
    <Paper 
      elevation={2}
      sx={{ 
        width: '100%', 
        textAlign: 'center', 
        py: 8,
        px: 3,
        borderRadius: 2,
        backgroundColor: 'background.paper',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2
      }}
    >
      {icon || (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <FolderIcon sx={{ fontSize: 60, color: 'primary.main', opacity: 0.7, mr: 1 }} />
          <AutoAwesomeIcon sx={{ fontSize: 30, color: 'secondary.main', ml: -3, mt: -1 }} />
        </Box>
      )}
      
      <Typography variant="h5" color="text.primary" gutterBottom fontWeight="medium">
        {title}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 550, mx: 'auto' }}>
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
 * Handles loading, displaying, and refreshing projects
 */
export default function ProjectsClientWrapper({ initialProjects = [], sessionToken }: ProjectsClientWrapperProps) {
  const [projects, setProjects] = useState<Project[]>(initialProjects || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshDisabled, setIsRefreshDisabled] = useState(false);
  const notifications = useNotifications();
  
  const refreshProjects = useCallback(async () => {
    if (isRefreshDisabled || !sessionToken) return;
    
    setLoading(true);
    setError(null);
    setIsRefreshDisabled(true);
    
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const projectsClient = apiFactory.getProjectsClient();
      const response = await projectsClient.getProjects();
      
      // Handle both array and paginated response formats consistently
      const projects = Array.isArray(response) ? response : (response as PaginatedResponse<Project>).data || [];
      setProjects(projects);
      
      notifications.show('Projects refreshed successfully', { severity: 'success' });
    } catch (error) {
      const errorMessage = (error as Error).message;
      setError(`Failed to refresh projects: ${errorMessage}`);
      notifications.show(`Failed to refresh projects: ${errorMessage}`, { severity: 'error' });
    } finally {
      setLoading(false);
      setTimeout(() => {
        setIsRefreshDisabled(false);
      }, 1000);
    }
  }, [sessionToken, isRefreshDisabled, notifications]);

  // Show error state if no session token
  if (!sessionToken) {
    return (
      <PageContainer title="Projects" breadcrumbs={[{ title: 'Projects', path: '/projects' }]}>
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
    <PageContainer title="Projects" breadcrumbs={[{ title: 'Projects', path: '/projects' }]}>
      {/* Header with actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button 
            onClick={refreshProjects}
            disabled={loading || isRefreshDisabled}
            startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
          >
            Refresh
          </Button>
          
          <Button 
            component={Link} 
            href="/projects/create-new" 
            variant="contained" 
            color="primary" 
            startIcon={<AddIcon />}
          >
            Create Project
          </Button>
        </Box>
      </Box>
      
      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {/* Projects grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {Array.isArray(projects) && projects.map((project) => (
          <Grid item key={project.id} xs={12} md={6} lg={4}>
            <ProjectCard project={project} />
          </Grid>
        ))}
        
        {(!Array.isArray(projects) || projects.length === 0) && !loading && (
          <Grid item xs={12}>
            <EmptyStateMessage
              title="No projects found"
              description="Create your first project to start building and testing your AI applications. Projects help you organize your work and collaborate with your team."
            />
          </Grid>
        )}
        
        {/* Loading placeholders */}
        {loading && (!Array.isArray(projects) || projects.length === 0) && (
          <>
            {[1, 2, 3].map((i) => (
              <Grid item key={`skeleton-${i}`} xs={12} md={6} lg={4}>
                <ProjectCard project={{} as Project} isLoading={true} />
              </Grid>
            ))}
          </>
        )}
      </Grid>
    </PageContainer>
  );
} 