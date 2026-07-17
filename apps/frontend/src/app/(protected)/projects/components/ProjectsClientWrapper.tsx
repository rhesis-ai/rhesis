'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Alert,
  CircularProgress,
  TablePagination,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { DeleteModal } from '@/components/common/DeleteModal';
import { Project, ProjectCreate } from '@/utils/api-client/interfaces/project';
import ProjectCard from './ProjectCard';
import ProjectCreateDrawer from './ProjectCreateDrawer';
import ProjectFilterDrawer, {
  type ProjectFilters,
  EMPTY_FILTERS,
  hasActiveProjectFilters,
  countActiveProjectFilters,
} from './ProjectFilterDrawer';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { AppsIcon } from '@/components/icons';
import { PageLayout } from '@/components/layout/PageLayout';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

type StatusFilter = 'all' | 'active' | 'inactive';

export default function ProjectsClientWrapper() {
  const { status } = useSession();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Project.READ
  );
  const canCreate = useCan(Capability.Project.CREATE);
  const canUpdateProject = useCan(Capability.Project.UPDATE);
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
  const { refresh: refreshActiveProjects } = useActiveProject();
  const isOnProjectTour = activeTour === 'project';
  const isProjectButtonDisabled = activeTour !== null && !isOnProjectTour;

  useOnboardingTour('project');

  // Fetch all projects on mount
  const fetchProjects = useCallback(async () => {
    if (!isAuthenticated(status)) return;
    try {
      setIsLoading(true);
      setError(null);
      const factory = new ApiClientFactory();
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
  }, [status]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreate = useCallback(
    async (payload: ProjectCreate) => {
      const factory = new ApiClientFactory();
      const client = factory.getProjectsClient();
      await client.createProject(payload);
      await Promise.all([fetchProjects(), refreshActiveProjects()]);
    },
    [fetchProjects, refreshActiveProjects]
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      const factory = new ApiClientFactory();
      const client = factory.getProjectsClient();
      await client.deleteProject(deleteTarget.id);
      setProjects(prev => prev.filter(p => p.id !== deleteTarget.id));
      await refreshActiveProjects();
    } catch (error) {
      console.error('Failed to delete project:', error);
    } finally {
      setDeleteTarget(null);
    }
  }, [deleteTarget, refreshActiveProjects]);

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

  const hasActiveFilters =
    search !== '' ||
    statusFilter !== 'all' ||
    hasActiveProjectFilters(activeFilters);

  const handleReset = () => {
    setSearch('');
    setStatusFilter('all');
    setActiveFilters(EMPTY_FILTERS);
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

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Projects" breadcrumbs={[]}>
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EntityEmptyState
          icon={AppsIcon}
          title="Authentication required"
          description="Please log in to view and manage your projects."
        />
      </PageLayout>
    );
  }

  const statusOptions: { value: StatusFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="projects" />;

  return (
    <PageLayout
      title="Projects"
      description="Organize your AI applications by grouping endpoints, tests, and results into projects."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Project.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create project"
              aria-label="Create project"
              data-tour="create-project-button"
              disabled={isProjectButtonDisabled}
              onClick={() => setCreateDrawerOpen(true)}
            />
          </Can>
        </FabGroup>
      }
    >
      <GridToolbar
        searchQuery={search}
        onSearchChange={v => {
          setSearch(v);
          setPage(0);
        }}
        searchPlaceholder="Search projects…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveProjectFilters(activeFilters)}
        activeFilterCount={countActiveProjectFilters(activeFilters)}
        {...directoryToolbarProps}
        middleContent={
          <ToolbarPillTabs
            tabs={statusOptions}
            activeValue={statusFilter}
            onChange={v => {
              setStatusFilter(v as StatusFilter);
              setPage(0);
            }}
          />
        }
      />

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
              <EntityEmptyState
                icon={AppsIcon}
                title="No projects match your filters"
                description="Try adjusting your search or status filter to find the projects you're looking for."
                actionLabel="Reset filters"
                onAction={handleReset}
              />
            ) : (
              <EntityEmptyState
                card
                icon={AppsIcon}
                title="No project yet"
                description="Create your first project to start organizing your AI applications. Projects help you group endpoints, tests, and results so you can collaborate with your team."
                actionLabel={canCreate ? 'Create project' : undefined}
                onAction={
                  canCreate ? () => setCreateDrawerOpen(true) : undefined
                }
                actionDisabled={isProjectButtonDisabled}
                enrichment={getEntityEmptyStateEnrichment('projects')}
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
                  onDelete={
                    canUpdateProject
                      ? () =>
                          setDeleteTarget({
                            id: String(project.id),
                            name: project.name,
                          })
                      : undefined
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
      />

      <ProjectFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={activeFilters}
        onApply={setActiveFilters}
      />

      {/* Delete confirmation dialog */}
      <DeleteModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Delete project?"
        message={
          <>
            Are you sure you want to delete{' '}
            <strong>{deleteTarget?.name}</strong>? This action cannot be undone.
          </>
        }
      />
    </PageLayout>
  );
}
