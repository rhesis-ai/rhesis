'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import Alert from '@mui/material/Alert';
import TablePagination from '@mui/material/TablePagination';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { useNotifications } from '@/components/common/NotificationContext';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import { TagsClient } from '@/utils/api-client/tags-client';
import { EntityType, type Tag } from '@/utils/api-client/interfaces/tag';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';
import RequirementCard from './RequirementCard';
import RequirementDrawer from './RequirementDrawer';
import RequirementMetricsViewer from './RequirementMetricsViewer';
import { generateCopyName } from '@/utils/entity-helpers';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { PsychologyIcon } from '@/components/icons';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import RequirementFilterDrawer, {
  type RequirementFilters,
  type MetricFilter,
  EMPTY_REQUIREMENT_FILTERS,
  hasActiveRequirementFilters,
  countActiveRequirementFilters,
} from './RequirementFilterDrawer';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { buildRequirementODataFilter } from '@/utils/odata-filter';

interface RequirementsClientProps {
  organizationId: UUID;
  userId?: UUID;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: RequirementWithMetrics[];
  initialTotalCount?: number;
}

export default function RequirementsClient({
  organizationId,
  userId,
  initialData,
  initialTotalCount = 0,
}: RequirementsClientProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const { status: sessionStatus } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Requirement.READ
  );
  const canCreateRequirement = useCan(Capability.Requirement.CREATE);

  // Accumulate tag names seen across page navigations for the filter drawer
  const tagNamesRef = React.useRef(new Set<string>());

  const [availableTagNames, setAvailableTagNames] = React.useState<string[]>(
    () => {
      if (!initialData) return [];
      initialData.forEach(requirement => {
        (requirement.tags ?? []).forEach(tag =>
          tagNamesRef.current.add(tag.name)
        );
      });
      return Array.from(tagNamesRef.current).sort((a, b) => a.localeCompare(b));
    }
  );

  // Drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editingRequirement, setEditingRequirement] = React.useState<{
    id: UUID | null;
    name: string;
    description: string;
    tagNames: string[];
  } | null>(null);
  const [isNewRequirement, setIsNewRequirement] = React.useState(false);
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string>();

  // Metrics viewer state
  const [metricsViewerOpen, setMetricsViewerOpen] = React.useState(false);
  const [viewingRequirement, setViewingRequirement] =
    React.useState<RequirementWithMetrics | null>(null);

  // Search & filter state
  const [searchQuery, setSearchQuery] = React.useState('');
  const [metricCountFilter, setMetricCountFilter] =
    React.useState<MetricFilter>('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = React.useState(false);
  const [drawerFilters, setDrawerFilters] = React.useState<RequirementFilters>(
    EMPTY_REQUIREMENT_FILTERS
  );

  // Reset to page 0 whenever filters change
  const filterFingerprint = React.useMemo(
    () =>
      JSON.stringify([searchQuery, metricCountFilter, drawerFilters.tagNames]),
    [searchQuery, metricCountFilter, drawerFilters.tagNames]
  );

  const {
    data: requirements,
    setData: setRequirements,
    totalCount,
    setTotalCount,
    isLoading,
    error,
    page,
    rowsPerPage,
    onPageChange: setPage,
    onRowsPerPageChange: handleRowsPerPageChange,
    refresh: handleRefresh,
  } = usePaginatedList<RequirementWithMetrics>({
    fetchPage: ({ skip, limit }) => {
      const requirementClient = new RequirementClient();
      const odataFilter = buildRequirementODataFilter({
        search: searchQuery,
        metricCount: metricCountFilter,
        tagNames: drawerFilters.tagNames,
      });
      return requirementClient.getRequirementsPage({
        skip,
        limit,
        sort_by: 'name',
        sort_order: 'asc',
        $filter: odataFilter,
      });
    },
    filterFingerprint,
    initialData,
    initialTotalCount,
    enabled: !permsLoading && canRead,
    onData: data => {
      data.forEach(requirement => {
        (requirement.tags ?? []).forEach(tag =>
          tagNamesRef.current.add(tag.name)
        );
      });
      setAvailableTagNames(
        Array.from(tagNamesRef.current).sort((a, b) => a.localeCompare(b))
      );
    },
    onError: () => {
      notifications.show('Failed to load requirements data', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    },
  });

  /**
   * Inserts a requirement into the current page in name order (matching the
   * directory's default sort) rather than relying on a re-fetch to reveal
   * it. A re-fetch of the current page can't be trusted to surface a
   * just-created item -- with server-side pagination, its name may sort
   * outside whatever page the user happens to be viewing.
   */
  /**
   * Only optimistically splices the new row into the *rendered* page when
   * we're on page 0: with server-side name sorting, a row created/duplicated
   * while viewing another page may not actually belong there, and we don't
   * have the adjacent pages' boundary names to know where it really sorts.
   * Elsewhere we still bump `totalCount` (so pagination controls reflect the
   * new row existing) and rely on the next real fetch to reveal it. Slicing
   * to `rowsPerPage` after inserting keeps the rendered page from exceeding
   * what the pagination controls advertise.
   */
  const insertRequirementSorted = (requirement: RequirementWithMetrics) => {
    setTotalCount(prev => prev + 1);
    if (page !== 0) return;
    setRequirements(prev => {
      const next = [...prev, requirement].sort((a, b) =>
        a.name.localeCompare(b.name)
      );
      return next.slice(0, rowsPerPage);
    });
  };

  const handleAddNewRequirement = () => {
    setEditingRequirement({
      id: null,
      name: '',
      description: '',
      tagNames: [],
    });
    setIsNewRequirement(true);
    setDrawerOpen(true);
  };

  const handleEditRequirement = (
    id: UUID,
    name: string,
    description: string,
    tagNames: string[] = []
  ) => {
    setEditingRequirement({ id, name, description, tagNames });
    setIsNewRequirement(false);
    setDrawerOpen(true);
  };

  const normalizeTagName = (name: string) => name.trim().toLowerCase();

  /**
   * Diff initial vs. new tag names and apply assign/remove against TagsClient.
   * Compares on normalized names (trim + lowercase) while sending trimmed
   * display values to the API.
   */
  const syncRequirementTags = async (
    requirementId: UUID,
    initialTags: Tag[],
    nextTagNames: string[]
  ): Promise<void> => {
    const normalizedNext = new Set(
      nextTagNames.map(normalizeTagName).filter(name => name.length > 0)
    );
    const normalizedInitial = new Map(
      initialTags.map(tag => [normalizeTagName(tag.name), tag])
    );

    const toRemove = initialTags.filter(
      tag => !normalizedNext.has(normalizeTagName(tag.name))
    );

    const seen = new Set<string>();
    const toAdd = nextTagNames
      .map(name => name.trim())
      .filter(name => name.length > 0)
      .filter(name => !normalizedInitial.has(normalizeTagName(name)))
      .filter(name => {
        const key = normalizeTagName(name);
        if (seen.has(key)) {
          return false;
        }
        seen.add(key);
        return true;
      });

    if (toRemove.length === 0 && toAdd.length === 0) {
      return;
    }

    const tagsClient = new TagsClient();

    await Promise.all(
      toRemove.map(tag =>
        tagsClient.removeTagFromEntity(
          EntityType.REQUIREMENT,
          requirementId,
          tag.id
        )
      )
    );

    await Promise.all(
      toAdd.map(name =>
        tagsClient.assignTagToEntity(EntityType.REQUIREMENT, requirementId, {
          name,
          organization_id: organizationId,
          ...(userId ? { user_id: userId } : {}),
        })
      )
    );
  };

  const handleSaveRequirement = async (
    name: string,
    description: string,
    tagNames: string[]
  ) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const requirementClient = new RequirementClient();
      let tagSyncFailed = false;

      if (isNewRequirement) {
        const created = await requirementClient.createRequirement({
          name: name.trim(),
          description: description?.trim() || null,
          organization_id: organizationId,
        });

        if (tagNames.length > 0) {
          try {
            await syncRequirementTags(created.id, [], tagNames);
          } catch {
            tagSyncFailed = true;
          }
        }

        const createdWithMetrics =
          await requirementClient.getRequirementWithMetrics(created.id);
        insertRequirementSorted(createdWithMetrics);

        notifications.show(
          tagSyncFailed
            ? 'Requirement created, but some tags failed to sync'
            : 'Requirement created successfully',
          {
            severity: tagSyncFailed ? 'warning' : 'success',
            autoHideDuration: 4000,
          }
        );
      } else if (editingRequirement && editingRequirement.id) {
        const editingId = editingRequirement.id;
        const existing = requirements.find(b => b.id === editingId);
        const updated = await requirementClient.updateRequirement(editingId, {
          name: name.trim(),
          description: description?.trim() || null,
        });

        try {
          await syncRequirementTags(editingId, existing?.tags ?? [], tagNames);
        } catch {
          tagSyncFailed = true;
        }

        const refreshed =
          await requirementClient.getRequirementWithMetrics(editingId);
        setRequirements(prev =>
          prev
            .map(b =>
              b.id === editingId
                ? {
                    ...b,
                    name: updated.name,
                    description: updated.description,
                    tags: refreshed.tags ?? [],
                  }
                : b
            )
            .sort((a, b) => a.name.localeCompare(b.name))
        );

        notifications.show(
          tagSyncFailed
            ? 'Requirement updated, but some tags failed to sync'
            : 'Requirement updated successfully',
          {
            severity: tagSyncFailed ? 'warning' : 'success',
            autoHideDuration: 4000,
          }
        );
      }

      setDrawerOpen(false);
    } catch (err) {
      setDrawerError(
        err instanceof Error ? err.message : 'Failed to save requirement'
      );
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDuplicateRequirement = async (
    id: UUID,
    name: string,
    description: string
  ) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const requirementClient = new RequirementClient();

      const created = await requirementClient.createRequirement({
        name: generateCopyName(name),
        description: description || null,
        organization_id: organizationId,
      });

      const createdWithMetrics =
        await requirementClient.getRequirementWithMetrics(created.id);
      insertRequirementSorted(createdWithMetrics);

      notifications.show('Requirement duplicated successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      setDrawerOpen(false);
    } catch (err) {
      setDrawerError(
        err instanceof Error ? err.message : 'Failed to duplicate requirement'
      );
      notifications.show('Failed to duplicate requirement', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDeleteRequirement = async () => {
    if (!isNewRequirement && editingRequirement && editingRequirement.id) {
      try {
        const requirementClient = new RequirementClient();

        const requirementToDelete = requirements.find(
          b => b.id === editingRequirement.id
        );
        if (requirementToDelete && requirementToDelete.metrics.length > 0) {
          notifications.show(
            'Cannot delete requirement with assigned metrics. Please remove all metrics first.',
            { severity: 'error', autoHideDuration: 6000 }
          );
          return;
        }

        await requirementClient.deleteRequirement(editingRequirement.id);

        setRequirements(prev =>
          prev.filter(b => b.id !== editingRequirement.id)
        );
        setTotalCount(prev => Math.max(0, prev - 1));

        notifications.show('Requirement deleted successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
        setDrawerOpen(false);
      } catch (err) {
        notifications.show(
          err instanceof Error ? err.message : 'Failed to delete requirement',
          { severity: 'error', autoHideDuration: 4000 }
        );
      }
    } else {
      setDrawerOpen(false);
    }
  };

  const handleViewMetrics = (requirement: RequirementWithMetrics) => {
    setViewingRequirement(requirement);
    setMetricsViewerOpen(true);
  };

  const handleMetricsViewerClose = () => {
    setMetricsViewerOpen(false);
    setViewingRequirement(null);
  };

  const handleMetricsViewerRefresh = (removedMetricId?: string) => {
    if (removedMetricId && viewingRequirement) {
      setRequirements(prev =>
        prev.map(requirement => {
          if (requirement.id === viewingRequirement.id) {
            return {
              ...requirement,
              metrics: requirement.metrics.filter(
                metric => metric.id !== removedMetricId
              ),
            };
          }
          return requirement;
        })
      );

      setViewingRequirement(prev => {
        if (prev) {
          return {
            ...prev,
            metrics: prev.metrics.filter(
              metric => metric.id !== removedMetricId
            ),
          };
        }
        return prev;
      });
    } else {
      handleRefresh();
    }
  };

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    metricCountFilter !== 'all' ||
    hasActiveRequirementFilters(drawerFilters);
  const editingRequirementId = !isNewRequirement
    ? editingRequirement?.id
    : null;

  const handleResetFilters = () => {
    setSearchQuery('');
    setMetricCountFilter('all');
    setDrawerFilters(EMPTY_REQUIREMENT_FILTERS);
  };

  const metricOptions: { value: MetricFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'has_metrics', label: 'Has Metrics' },
    { value: 'no_metrics', label: 'No Metrics' },
  ];

  // First load — no data at all yet, show a full-page spinner
  const isInitialLoad =
    isLoading && requirements.length === 0 && totalCount === 0;

  if (isInitialLoad) {
    return (
      <PageLayout title="Requirements" breadcrumbs={[]}>
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
          <Typography>Loading requirements...</Typography>
        </Box>
      </PageLayout>
    );
  }

  // Auth error state
  if (!isAuthenticated(sessionStatus)) {
    return (
      <PageLayout title="Requirements" breadcrumbs={[]}>
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EntityEmptyState
          icon={PsychologyIcon}
          title="Authentication required"
          description="Please log in to view and manage your requirements."
        />
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="requirements" />;

  return (
    <PageLayout
      title="Requirements"
      description="Requirements are atomic expectations for your application, measured through one or more metrics to determine if requirements are met."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Requirement.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create requirement"
              aria-label="Create requirement"
              onClick={handleAddNewRequirement}
            />
          </Can>
        </FabGroup>
      }
    >
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search requirements…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveRequirementFilters(drawerFilters)}
        activeFilterCount={countActiveRequirementFilters(drawerFilters)}
        {...directoryToolbarProps}
        middleContent={
          <ToolbarPillTabs
            tabs={metricOptions}
            activeValue={metricCountFilter}
            onChange={v => setMetricCountFilter(v as MetricFilter)}
          />
        }
      />

      {/* Error state */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Subtle loading indicator for subsequent fetches — always
          mounted so its height never shifts the grid below */}
      <LinearProgress
        sx={{
          mb: 1,
          borderRadius: theme => theme.shape.borderRadius,
          visibility: isLoading ? 'visible' : 'hidden',
        }}
      />

      {/* Requirements grid / empty states */}
      {requirements.length === 0 ? (
        hasActiveFilters ? (
          <EntityEmptyState
            icon={PsychologyIcon}
            title="No requirements match your filters"
            description="Try adjusting your search or filter to find the requirements you're looking for."
            actionLabel="Reset filters"
            onAction={handleResetFilters}
          />
        ) : (
          <EntityEmptyState
            card
            icon={PsychologyIcon}
            title="No requirement yet"
            description="Create your first requirement to define atomic expectations for your AI applications. Requirements are measured through metrics to ensure your requirements are met."
            actionLabel={
              canCreateRequirement ? 'Create requirement' : undefined
            }
            onAction={
              canCreateRequirement ? handleAddNewRequirement : undefined
            }
            enrichment={getEntityEmptyStateEnrichment('requirements')}
          />
        )
      ) : (
        <Box
          sx={theme => ({
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: '1fr 1fr',
              md: 'repeat(3, 1fr)',
            },
            gap: theme.spacing(3),
            mb: 4,
          })}
        >
          {requirements.map(requirement => (
            <RequirementCard
              key={requirement.id}
              requirement={requirement}
              onClick={() =>
                router.push(`${API_ENDPOINTS.requirements}/${requirement.id}`)
              }
              onEdit={() =>
                handleEditRequirement(
                  requirement.id,
                  requirement.name,
                  requirement.description || '',
                  (requirement.tags ?? []).map(t => t.name)
                )
              }
              onDuplicate={() =>
                handleDuplicateRequirement(
                  requirement.id,
                  requirement.name,
                  requirement.description || ''
                )
              }
              onViewMetrics={() => handleViewMetrics(requirement)}
              onRefresh={handleRefresh}
            />
          ))}
        </Box>
      )}
      {totalCount > 0 && (
        <TablePagination
          component="div"
          count={totalCount}
          page={page}
          onPageChange={(_event, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={event =>
            handleRowsPerPageChange(parseInt(event.target.value, 10))
          }
          rowsPerPageOptions={[25, 50, 100]}
          labelRowsPerPage="Requirements per page:"
          sx={{ mb: 2 }}
        />
      )}

      {/* Requirement Edit Drawer */}
      {editingRequirement && (
        <RequirementDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          name={editingRequirement.name}
          description={editingRequirement.description}
          initialTagNames={editingRequirement.tagNames}
          tagSuggestions={availableTagNames}
          onSave={handleSaveRequirement}
          onDuplicate={
            editingRequirementId
              ? () =>
                  handleDuplicateRequirement(
                    editingRequirementId,
                    editingRequirement.name,
                    editingRequirement.description
                  )
              : undefined
          }
          onDelete={
            editingRequirementId &&
            requirements.find(b => b.id === editingRequirementId)?.metrics
              ?.length === 0
              ? handleDeleteRequirement
              : undefined
          }
          isNew={isNewRequirement}
          loading={drawerLoading}
          error={drawerError}
        />
      )}

      {/* Requirement Metrics Viewer */}
      <RequirementMetricsViewer
        open={metricsViewerOpen}
        onClose={handleMetricsViewerClose}
        requirement={viewingRequirement}
        onRefresh={handleMetricsViewerRefresh}
      />

      <RequirementFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        availableTagNames={availableTagNames}
        onApply={f => {
          setDrawerFilters(f);
          setMetricCountFilter(f.metricCount);
        }}
      />
    </PageLayout>
  );
}
