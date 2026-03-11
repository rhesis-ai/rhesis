'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Button,
  Alert,
  Paper,
  CircularProgress,
  ButtonGroup,
  TablePagination,
} from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectCard from './ProjectCard';
import AddIcon from '@mui/icons-material/Add';
import FolderIcon from '@mui/icons-material/Folder';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ListIcon from '@mui/icons-material/List';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DoNotDisturbAltIcon from '@mui/icons-material/DoNotDisturbAlt';
import Link from 'next/link';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import styles from '@/styles/ProjectsClientWrapper.module.css';
import SearchAndFilterBar from '@/components/common/SearchAndFilterBar';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

type StatusFilter = 'all' | 'active' | 'inactive';

interface EmptyStateMessageProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
}

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

interface ProjectsClientWrapperProps {
  sessionToken: string;
}

export default function ProjectsClientWrapper({
  sessionToken,
}: ProjectsClientWrapperProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  // Pagination state
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const { markStepComplete, progress, activeTour } = useOnboarding();
  const isOnProjectTour = activeTour === 'project';
  const isProjectButtonDisabled = activeTour !== null && !isOnProjectTour;

  useOnboardingTour('project');

  // Fetch all projects on mount
  const fetchProjects = useCallback(async () => {
    if (!sessionToken) return;
    try {
      setIsLoading(true);
      setError(null);
      const factory = new ApiClientFactory(sessionToken);
      const client = factory.getProjectsClient();
      const data = await client.getAllProjects({
        sort_by: 'name',
        sort_order: 'asc',
      });
      setProjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Mark onboarding step complete when projects are loaded
  useEffect(() => {
    if (projects.length > 0 && !progress.projectCreated) {
      markStepComplete('projectCreated');
    }
  }, [projects.length, progress.projectCreated, markStepComplete]);

  // Apply filters
  const filteredProjects = projects.filter(project => {
    const searchLower = search.toLowerCase();
    const nameMatch = project.name?.toLowerCase().includes(searchLower);
    const descMatch = project.description?.toLowerCase().includes(searchLower);
    const searchMatch = !search || nameMatch || descMatch;

    const statusMatch =
      statusFilter === 'all' ||
      (statusFilter === 'active' && project.is_active !== false) ||
      (statusFilter === 'inactive' && project.is_active === false);

    return searchMatch && statusMatch;
  });

  const hasActiveFilters = search !== '' || statusFilter !== 'all';

  const handleReset = () => {
    setSearch('');
    setStatusFilter('all');
    setPage(0);
  };

  // Clamp current page when the filtered list shrinks
  useEffect(() => {
    const lastPage = Math.max(
      0,
      Math.ceil(filteredProjects.length / rowsPerPage) - 1
    );
    if (page > lastPage) setPage(lastPage);
  }, [filteredProjects.length, rowsPerPage, page]);

  const paginatedProjects = filteredProjects.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  if (!sessionToken) {
    return (
      <PageContainer title="Projects" breadcrumbs={[]}>
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
    <PageContainer title="Projects" breadcrumbs={[]}>
      {/* Description */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body1" color="text.secondary">
          Projects group your endpoints for testing and evaluation. Use them to
          organise your AI applications and collaborate with your team.
        </Typography>
      </Box>

      <SearchAndFilterBar
        searchValue={search}
        onSearchChange={value => {
          setSearch(value);
          setPage(0);
        }}
        hasActiveFilters={hasActiveFilters}
        onReset={hasActiveFilters ? handleReset : undefined}
        searchPlaceholder="Search projects..."
        renderAddButton={() => (
          <Button
            component={isProjectButtonDisabled ? 'button' : Link}
            href={isProjectButtonDisabled ? undefined : '/projects/create-new'}
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            data-tour="create-project-button"
            disabled={isProjectButtonDisabled}
            sx={{ whiteSpace: 'nowrap' }}
          >
            Create Project
          </Button>
        )}
      >
        {/* Status filter buttons */}
        <ButtonGroup size="small" variant="outlined">
          <Button
            onClick={() => {
              setStatusFilter('all');
              setPage(0);
            }}
            variant={statusFilter === 'all' ? 'contained' : 'outlined'}
            startIcon={<ListIcon fontSize="small" />}
          >
            All
          </Button>
          <Button
            onClick={() => {
              setStatusFilter('active');
              setPage(0);
            }}
            variant={statusFilter === 'active' ? 'contained' : 'outlined'}
            startIcon={<CheckCircleIcon fontSize="small" />}
          >
            Active
          </Button>
          <Button
            onClick={() => {
              setStatusFilter('inactive');
              setPage(0);
            }}
            variant={statusFilter === 'inactive' ? 'contained' : 'outlined'}
            startIcon={<DoNotDisturbAltIcon fontSize="small" />}
          >
            Inactive
          </Button>
        </ButtonGroup>
      </SearchAndFilterBar>

      {/* Loading state */}
      {isLoading && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            py: 8,
            gap: 2,
          }}
        >
          <CircularProgress size={24} />
          <Typography>Loading projects…</Typography>
        </Box>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Projects grid */}
      {!isLoading && !error && (
        <>
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {paginatedProjects.map(project => (
              <Grid key={project.id} size={{ xs: 12, md: 6, lg: 4 }}>
                <ProjectCard project={project} />
              </Grid>
            ))}

            {filteredProjects.length === 0 && (
              <Grid size={12}>
                {hasActiveFilters ? (
                  <EmptyStateMessage
                    title="No projects match your filters"
                    description="Try adjusting your search or status filter to find the projects you're looking for."
                  />
                ) : (
                  <EmptyStateMessage
                    title="No projects found"
                    description="Create your first project to start building and testing your AI applications. Projects help you organize your work and collaborate with your team."
                  />
                )}
              </Grid>
            )}
          </Grid>

          {/* Pagination — only shown when there are enough results */}
          {filteredProjects.length > rowsPerPage && (
            <TablePagination
              component="div"
              count={filteredProjects.length}
              page={page}
              onPageChange={(_event, newPage) => setPage(newPage)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={event => {
                setRowsPerPage(parseInt(event.target.value, 10));
                setPage(0);
              }}
              rowsPerPageOptions={[25, 50, 100]}
              labelRowsPerPage="Projects per page:"
              sx={{ mb: 2 }}
            />
          )}
        </>
      )}
    </PageContainer>
  );
}
