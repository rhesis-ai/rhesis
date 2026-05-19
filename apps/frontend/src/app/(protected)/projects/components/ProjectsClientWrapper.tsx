'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Alert,
  Paper,
  CircularProgress,
  IconButton,
  TablePagination,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import { Project, ProjectCreate } from '@/utils/api-client/interfaces/project';
import { GREYSCALE, BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import ProjectCard from './ProjectCard';
import ProjectCreateDrawer from './ProjectCreateDrawer';
import ProjectFilterDrawer, {
  type ProjectFilters,
  EMPTY_FILTERS,
} from './ProjectFilterDrawer';
import AddIcon from '@mui/icons-material/Add';
import FolderIcon from '@mui/icons-material/Folder';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TuneIcon from '@mui/icons-material/TuneOutlined';
import { SearchPill } from '@/components/common/SearchPill';
import { PageLayout } from '@/components/layout/PageLayout';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import styles from '@/styles/ProjectsClientWrapper.module.css';
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
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [activeFilters, setActiveFilters] =
    useState<ProjectFilters>(EMPTY_FILTERS);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);

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

  const handleCreate = useCallback(
    async (payload: ProjectCreate) => {
      const factory = new ApiClientFactory(sessionToken);
      const client = factory.getProjectsClient();
      await client.createProject(payload);
      await fetchProjects();
    },
    [sessionToken, fetchProjects]
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      const factory = new ApiClientFactory(sessionToken);
      const client = factory.getProjectsClient();
      await client.deleteProject(deleteTarget.id);
      setProjects(prev => prev.filter(p => p.id !== deleteTarget.id));
    } catch {
    } finally {
      setDeleteTarget(null);
    }
  }, [deleteTarget, sessionToken]);

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

    const drawerStatusMatch =
      activeFilters.activeStatus === null ||
      (activeFilters.activeStatus === true && project.is_active !== false) ||
      (activeFilters.activeStatus === false && project.is_active === false);

    const envMatch =
      activeFilters.environments.length === 0 ||
      (project.environment != null &&
        activeFilters.environments.includes(project.environment));

    return searchMatch && statusMatch && drawerStatusMatch && envMatch;
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
      <PageLayout title="Projects" breadcrumbs={[]}>
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EmptyStateMessage
          title="Authentication Required"
          description="Please log in to view and manage your projects."
        />
      </PageLayout>
    );
  }

  const fabSx = {
    bgcolor: 'primary.main',
    color: '#fff',
    borderRadius: BORDER_RADIUS.pill,
    p: '12px',
    boxShadow: ELEVATION.xs,
    '&:hover': { bgcolor: 'primary.dark' },
    '& .MuiSvgIcon-root': { fontSize: 28 },
  } as const;

  const statusOptions: { value: StatusFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  return (
    <PageLayout
      title="Projects"
      breadcrumbs={[]}
      actions={
        <IconButton
          sx={fabSx}
          aria-label="Create project"
          data-tour="create-project-button"
          disabled={isProjectButtonDisabled}
          onClick={() => setCreateDrawerOpen(true)}
        >
          <AddIcon />
        </IconButton>
      }
    >
      {/* Figma Toolbar (841:38547) — 3-col grid keeps pills truly centered */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          mb: 3,
          gap: 2,
        }}
      >
        {/* Left: Filter icon + Search pill */}
        <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <IconButton
            aria-label="Filter"
            onClick={() => setFilterDrawerOpen(true)}
            sx={{
              bgcolor: 'primary.main',
              color: '#fff',
              borderRadius: BORDER_RADIUS.sm,
              p: '9px',
              '&:hover': { bgcolor: 'primary.dark' },
              '& .MuiSvgIcon-root': { fontSize: 20 },
            }}
          >
            <TuneIcon />
          </IconButton>

          {/* Search pill */}
          <SearchPill
            value={search}
            onChange={v => {
              setSearch(v);
              setPage(0);
            }}
            placeholder="Search projects…"
          />
        </Box>

        {/* Center: Status pill tabs — display:flex + margin:auto keeps them centered in the grid cell */}
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          {statusOptions.map(({ value, label }, idx) => {
            const selected = statusFilter === value;
            const isFirst = idx === 0;
            const isLast = idx === statusOptions.length - 1;
            return (
              <Box
                key={value}
                component="button"
                onClick={() => {
                  setStatusFilter(value);
                  setPage(0);
                }}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  px: '16px',
                  py: '8px',
                  fontSize: 14,
                  fontWeight: 700,
                  lineHeight: '22px',
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'primary.main',
                  borderLeft: isFirst ? '1px solid' : 'none',
                  borderRight: isLast ? '1px solid' : 'none',
                  borderRadius: isFirst
                    ? '999px 0 0 999px'
                    : isLast
                      ? '0 999px 999px 0'
                      : 0,
                  bgcolor: selected ? 'primary.main' : 'transparent',
                  color: selected ? '#fff' : 'primary.main',
                  transition: 'background-color 0.15s, color 0.15s',
                  '&:hover': {
                    bgcolor: selected ? 'primary.dark' : 'rgba(0,128,175,0.06)',
                  },
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </Box>
            );
          })}
        </Box>
      </Box>

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
          {filteredProjects.length === 0 ? (
            hasActiveFilters ? (
              <EmptyStateMessage
                title="No projects match your filters"
                description="Try adjusting your search or status filter to find the projects you're looking for."
              />
            ) : (
              <EmptyStateMessage
                title="No projects found"
                description="Create your first project to start building and testing your AI applications. Projects help you organize your work and collaborate with your team."
              />
            )
          ) : (
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: '1fr 1fr',
                  md: 'repeat(3, 1fr)',
                },
                gap: '24px',
                mb: 4,
              }}
            >
              {paginatedProjects.map(project => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onDelete={() =>
                    setDeleteTarget({
                      id: String(project.id),
                      name: project.name,
                    })
                  }
                />
              ))}
            </Box>
          )}

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
      <ProjectCreateDrawer
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        onCreate={handleCreate}
        sessionToken={sessionToken}
      />

      <ProjectFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={activeFilters}
        onApply={setActiveFilters}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete project?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete{' '}
            <strong>{deleteTarget?.name}</strong>? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={confirmDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </PageLayout>
  );
}
