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
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { TagsClient } from '@/utils/api-client/tags-client';
import { EntityType, type Tag } from '@/utils/api-client/interfaces/tag';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';
import BehaviorCard from './BehaviorCard';
import BehaviorDrawer from './BehaviorDrawer';
import BehaviorMetricsViewer from './BehaviorMetricsViewer';
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
import BehaviorFilterDrawer, {
  type BehaviorFilters,
  type MetricFilter,
  EMPTY_BEHAVIOR_FILTERS,
  hasActiveBehaviorFilters,
  countActiveBehaviorFilters,
} from './BehaviorFilterDrawer';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';
import { buildBehaviorODataFilter } from '@/utils/odata-filter';

interface BehaviorsClientProps {
  organizationId: UUID;
  userId?: UUID;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: BehaviorWithMetrics[];
  initialTotalCount?: number;
}

export default function BehaviorsClient({
  organizationId,
  userId,
  initialData,
  initialTotalCount = 0,
}: BehaviorsClientProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const { status: sessionStatus } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Behavior.READ
  );
  const canCreateBehavior = useCan(Capability.Behavior.CREATE);

  // Accumulate tag names seen across page navigations for the filter drawer
  const tagNamesRef = React.useRef(new Set<string>());

  // Data state — seeded from the server-fetched first page when available
  const [behaviors, setBehaviors] = React.useState<BehaviorWithMetrics[]>(
    initialData ?? []
  );
  const [totalCount, setTotalCount] = React.useState(initialTotalCount);
  const [isLoading, setIsLoading] = React.useState(initialData === undefined);
  const [error, setError] = React.useState<string | null>(null);

  // Pagination
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(25);

  const [availableTagNames, setAvailableTagNames] = React.useState<string[]>(
    () => {
      if (!initialData) return [];
      initialData.forEach(behavior => {
        (behavior.tags ?? []).forEach(tag => tagNamesRef.current.add(tag.name));
      });
      return Array.from(tagNamesRef.current).sort((a, b) => a.localeCompare(b));
    }
  );

  // Drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editingBehavior, setEditingBehavior] = React.useState<{
    id: UUID | null;
    name: string;
    description: string;
    tagNames: string[];
  } | null>(null);
  const [isNewBehavior, setIsNewBehavior] = React.useState(false);
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string>();

  // Metrics viewer state
  const [metricsViewerOpen, setMetricsViewerOpen] = React.useState(false);
  const [viewingBehavior, setViewingBehavior] =
    React.useState<BehaviorWithMetrics | null>(null);

  // Search & filter state
  const [searchQuery, setSearchQuery] = React.useState('');
  const [metricCountFilter, setMetricCountFilter] =
    React.useState<MetricFilter>('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = React.useState(false);
  const [drawerFilters, setDrawerFilters] = React.useState<BehaviorFilters>(
    EMPTY_BEHAVIOR_FILTERS
  );

  // Refresh key for manual refresh
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Reset to page 0 whenever filters change
  const filterFingerprint = React.useMemo(
    () =>
      JSON.stringify([searchQuery, metricCountFilter, drawerFilters.tagNames]),
    [searchQuery, metricCountFilter, drawerFilters.tagNames]
  );

  // Identifies the request whose result is currently reflected in
  // `behaviors`/`totalCount`. Seeded with the server-fetched first page's
  // signature (page 0, default size, no filters, refreshKey 0 -- exactly
  // what `page`/`rowsPerPage`/`filterFingerprint`/`refreshKey` hold on this
  // first render) when the server provided initial data. The fetch effect
  // below compares against this on every run rather than consuming a
  // one-shot flag, so it stays correct under React 18 Strict Mode's dev-only
  // double-invoke of mount effects -- both invocations compute the same
  // signature and both no-op, instead of the second one slipping through a
  // "consumed" ref.
  //
  // `sessionStatus` is part of the key so a run that lands while the session
  // is still `loading` doesn't "claim" the same key a later `authenticated`
  // run would use -- otherwise that later run would see a match and skip the
  // fetch entirely, leaving the page stuck.
  const loadedRequestKeyRef = React.useRef<string | null>(
    initialData !== undefined
      ? `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}|${sessionStatus}`
      : null
  );

  React.useEffect(() => {
    setPage(0);
  }, [filterFingerprint]);

  React.useEffect(() => {
    const requestKey = `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}|${sessionStatus}`;
    if (loadedRequestKeyRef.current === requestKey) {
      return;
    }
    loadedRequestKeyRef.current = requestKey;

    let cancelled = false;

    const fetchBehaviors = async () => {
      if (!isAuthenticated(sessionStatus)) {
        // Keep spinner while session is still loading; stop it on auth failure
        if (!isSessionLoading(sessionStatus)) {
          setIsLoading(false);
        }
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        const behaviorClient = new BehaviorClient();
        const odataFilter = buildBehaviorODataFilter({
          search: searchQuery,
          metricCount: metricCountFilter,
          tagNames: drawerFilters.tagNames,
        });

        const response = await behaviorClient.getBehaviorsPage({
          skip: page * rowsPerPage,
          limit: rowsPerPage,
          sort_by: 'name',
          sort_order: 'asc',
          $filter: odataFilter,
        });

        if (cancelled) return;

        setBehaviors(response.data);
        setTotalCount(response.pagination.totalCount);

        response.data.forEach(behavior => {
          (behavior.tags ?? []).forEach(tag =>
            tagNamesRef.current.add(tag.name)
          );
        });
        setAvailableTagNames(
          Array.from(tagNamesRef.current).sort((a, b) => a.localeCompare(b))
        );
      } catch (err) {
        if (cancelled) return;
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch behaviors';
        setError(errorMessage);
        notifications.show('Failed to load behaviors data', {
          severity: 'error',
          autoHideDuration: 4000,
        });
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchBehaviors();
    return () => {
      cancelled = true;
    };
    // filterFingerprint captures search/metricCount/tagNames; no need to list them individually
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    page,
    rowsPerPage,
    filterFingerprint,
    refreshKey,
    sessionStatus,
    notifications,
  ]);

  // Clamp page when the result set shrinks below the current page (e.g. after delete)
  React.useEffect(() => {
    if (totalCount === 0) return;
    const lastPage = Math.max(0, Math.ceil(totalCount / rowsPerPage) - 1);
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [totalCount, rowsPerPage, page]);

  const handleAddNewBehavior = () => {
    setEditingBehavior({ id: null, name: '', description: '', tagNames: [] });
    setIsNewBehavior(true);
    setDrawerOpen(true);
  };

  const handleEditBehavior = (
    id: UUID,
    name: string,
    description: string,
    tagNames: string[] = []
  ) => {
    setEditingBehavior({ id, name, description, tagNames });
    setIsNewBehavior(false);
    setDrawerOpen(true);
  };

  const normalizeTagName = (name: string) => name.trim().toLowerCase();

  /**
   * Diff initial vs. new tag names and apply assign/remove against TagsClient.
   * Compares on normalized names (trim + lowercase) while sending trimmed
   * display values to the API.
   */
  const syncBehaviorTags = async (
    behaviorId: UUID,
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
        tagsClient.removeTagFromEntity(EntityType.BEHAVIOR, behaviorId, tag.id)
      )
    );

    await Promise.all(
      toAdd.map(name =>
        tagsClient.assignTagToEntity(EntityType.BEHAVIOR, behaviorId, {
          name,
          organization_id: organizationId,
          ...(userId ? { user_id: userId } : {}),
        })
      )
    );
  };

  const handleSaveBehavior = async (
    name: string,
    description: string,
    tagNames: string[]
  ) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const behaviorClient = new BehaviorClient();
      let tagSyncFailed = false;

      if (isNewBehavior) {
        const created = await behaviorClient.createBehavior({
          name: name.trim(),
          description: description?.trim() || null,
          organization_id: organizationId,
        });

        if (tagNames.length > 0) {
          try {
            await syncBehaviorTags(created.id, [], tagNames);
          } catch {
            tagSyncFailed = true;
          }
        }

        // Re-fetch the current page rather than splicing the new item into
        // local state -- with server-side pagination/sorting, the new
        // behavior may not belong on the page the user is viewing.
        handleRefresh();

        notifications.show(
          tagSyncFailed
            ? 'Behavior created, but some tags failed to sync'
            : 'Behavior created successfully',
          {
            severity: tagSyncFailed ? 'warning' : 'success',
            autoHideDuration: 4000,
          }
        );
      } else if (editingBehavior && editingBehavior.id) {
        const editingId = editingBehavior.id;
        const existing = behaviors.find(b => b.id === editingId);
        await behaviorClient.updateBehavior(editingId, {
          name: name.trim(),
          description: description?.trim() || null,
        });

        try {
          await syncBehaviorTags(editingId, existing?.tags ?? [], tagNames);
        } catch {
          tagSyncFailed = true;
        }

        handleRefresh();

        notifications.show(
          tagSyncFailed
            ? 'Behavior updated, but some tags failed to sync'
            : 'Behavior updated successfully',
          {
            severity: tagSyncFailed ? 'warning' : 'success',
            autoHideDuration: 4000,
          }
        );
      }

      setDrawerOpen(false);
    } catch (err) {
      setDrawerError(
        err instanceof Error ? err.message : 'Failed to save behavior'
      );
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDuplicateBehavior = async (
    id: UUID,
    name: string,
    description: string
  ) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const behaviorClient = new BehaviorClient();

      await behaviorClient.createBehavior({
        name: generateCopyName(name),
        description: description || null,
        organization_id: organizationId,
      });

      handleRefresh();

      notifications.show('Behavior duplicated successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      setDrawerOpen(false);
    } catch (err) {
      setDrawerError(
        err instanceof Error ? err.message : 'Failed to duplicate behavior'
      );
      notifications.show('Failed to duplicate behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDeleteBehavior = async () => {
    if (!isNewBehavior && editingBehavior && editingBehavior.id) {
      try {
        const behaviorClient = new BehaviorClient();

        const behaviorToDelete = behaviors.find(
          b => b.id === editingBehavior.id
        );
        if (behaviorToDelete && behaviorToDelete.metrics.length > 0) {
          notifications.show(
            'Cannot delete behavior with assigned metrics. Please remove all metrics first.',
            { severity: 'error', autoHideDuration: 6000 }
          );
          return;
        }

        await behaviorClient.deleteBehavior(editingBehavior.id);

        handleRefresh();

        notifications.show('Behavior deleted successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
        setDrawerOpen(false);
      } catch (err) {
        notifications.show(
          err instanceof Error ? err.message : 'Failed to delete behavior',
          { severity: 'error', autoHideDuration: 4000 }
        );
      }
    } else {
      setDrawerOpen(false);
    }
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  const handleViewMetrics = (behavior: BehaviorWithMetrics) => {
    setViewingBehavior(behavior);
    setMetricsViewerOpen(true);
  };

  const handleMetricsViewerClose = () => {
    setMetricsViewerOpen(false);
    setViewingBehavior(null);
  };

  const handleMetricsViewerRefresh = (removedMetricId?: string) => {
    if (removedMetricId && viewingBehavior) {
      setBehaviors(prev =>
        prev.map(behavior => {
          if (behavior.id === viewingBehavior.id) {
            return {
              ...behavior,
              metrics: behavior.metrics.filter(
                metric => metric.id !== removedMetricId
              ),
            };
          }
          return behavior;
        })
      );

      setViewingBehavior(prev => {
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
      setRefreshKey(prev => prev + 1);
    }
  };

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    metricCountFilter !== 'all' ||
    hasActiveBehaviorFilters(drawerFilters);
  const editingBehaviorId = !isNewBehavior ? editingBehavior?.id : null;

  const handleResetFilters = () => {
    setSearchQuery('');
    setMetricCountFilter('all');
    setDrawerFilters(EMPTY_BEHAVIOR_FILTERS);
  };

  const metricOptions: { value: MetricFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'has_metrics', label: 'Has Metrics' },
    { value: 'no_metrics', label: 'No Metrics' },
  ];

  // First load — no data at all yet, show a full-page spinner
  const isInitialLoad = isLoading && behaviors.length === 0 && totalCount === 0;

  if (isInitialLoad) {
    return (
      <PageLayout title="Behaviors" breadcrumbs={[]}>
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
          <Typography>Loading behaviors...</Typography>
        </Box>
      </PageLayout>
    );
  }

  // Auth error state
  if (!isAuthenticated(sessionStatus)) {
    return (
      <PageLayout title="Behaviors" breadcrumbs={[]}>
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EntityEmptyState
          icon={PsychologyIcon}
          title="Authentication required"
          description="Please log in to view and manage your behaviors."
        />
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="behaviors" />;

  return (
    <PageLayout
      title="Behaviors"
      description="Behaviors are atomic expectations for your application, measured through one or more metrics to determine if requirements are met."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Behavior.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create behavior"
              aria-label="Create behavior"
              onClick={handleAddNewBehavior}
            />
          </Can>
        </FabGroup>
      }
    >
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search behaviors…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveBehaviorFilters(drawerFilters)}
        activeFilterCount={countActiveBehaviorFilters(drawerFilters)}
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

      {/* Behaviors grid / empty states */}
      {behaviors.length === 0 ? (
        hasActiveFilters ? (
          <EntityEmptyState
            icon={PsychologyIcon}
            title="No behaviors match your filters"
            description="Try adjusting your search or filter to find the behaviors you're looking for."
            actionLabel="Reset filters"
            onAction={handleResetFilters}
          />
        ) : (
          <EntityEmptyState
            card
            icon={PsychologyIcon}
            title="No behavior yet"
            description="Create your first behavior to define atomic expectations for your AI applications. Behaviors are measured through metrics to ensure your requirements are met."
            actionLabel={canCreateBehavior ? 'Create behavior' : undefined}
            onAction={canCreateBehavior ? handleAddNewBehavior : undefined}
            enrichment={getEntityEmptyStateEnrichment('behaviors')}
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
          {behaviors.map(behavior => (
            <BehaviorCard
              key={behavior.id}
              behavior={behavior}
              onClick={() => router.push(`/behaviors/${behavior.id}`)}
              onEdit={() =>
                handleEditBehavior(
                  behavior.id,
                  behavior.name,
                  behavior.description || '',
                  (behavior.tags ?? []).map(t => t.name)
                )
              }
              onDuplicate={() =>
                handleDuplicateBehavior(
                  behavior.id,
                  behavior.name,
                  behavior.description || ''
                )
              }
              onViewMetrics={() => handleViewMetrics(behavior)}
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
          onRowsPerPageChange={event => {
            setRowsPerPage(parseInt(event.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100]}
          labelRowsPerPage="Behaviors per page:"
          sx={{ mb: 2 }}
        />
      )}

      {/* Behavior Edit Drawer */}
      {editingBehavior && (
        <BehaviorDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          name={editingBehavior.name}
          description={editingBehavior.description}
          initialTagNames={editingBehavior.tagNames}
          tagSuggestions={availableTagNames}
          onSave={handleSaveBehavior}
          onDuplicate={
            editingBehaviorId
              ? () =>
                  handleDuplicateBehavior(
                    editingBehaviorId,
                    editingBehavior.name,
                    editingBehavior.description
                  )
              : undefined
          }
          onDelete={
            editingBehaviorId &&
            behaviors.find(b => b.id === editingBehaviorId)?.metrics?.length ===
              0
              ? handleDeleteBehavior
              : undefined
          }
          isNew={isNewBehavior}
          loading={drawerLoading}
          error={drawerError}
        />
      )}

      {/* Behavior Metrics Viewer */}
      <BehaviorMetricsViewer
        open={metricsViewerOpen}
        onClose={handleMetricsViewerClose}
        behavior={viewingBehavior}
        onRefresh={handleMetricsViewerRefresh}
      />

      <BehaviorFilterDrawer
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
