'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import AddIcon from '@mui/icons-material/Add';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarSx,
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
import { PsychologyIcon } from '@/components/icons';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import BehaviorFilterDrawer, {
  type BehaviorFilters,
  type MetricFilter,
  EMPTY_BEHAVIOR_FILTERS,
  hasActiveBehaviorFilters,
} from './BehaviorFilterDrawer';

interface BehaviorsClientProps {
  sessionToken: string;
  organizationId: UUID;
  userId?: UUID;
  sessionStatus?: 'loading' | 'authenticated' | 'unauthenticated';
}

export default function BehaviorsClient({
  sessionToken,
  organizationId,
  userId,
  sessionStatus,
}: BehaviorsClientProps) {
  const notifications = useNotifications();

  // Data state
  const [behaviors, setBehaviors] = React.useState<BehaviorWithMetrics[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

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

  const lastSessionTokenRef = React.useRef<string | null>(null);
  const hasFetchedRef = React.useRef(false);

  React.useEffect(() => {
    const fetchBehaviors = async () => {
      if (!sessionToken) {
        // Keep spinner while session is still loading; stop it on auth failure
        if (sessionStatus !== 'loading') {
          setIsLoading(false);
        }
        return;
      }

      if (
        refreshKey === 0 &&
        lastSessionTokenRef.current !== null &&
        lastSessionTokenRef.current === sessionToken &&
        hasFetchedRef.current
      ) {
        return;
      }

      lastSessionTokenRef.current = sessionToken;

      try {
        setIsLoading(true);
        setError(null);

        const behaviorClient = new BehaviorClient(sessionToken);
        const behaviorsList = await behaviorClient.getBehaviorsWithMetrics({
          limit: 100,
        });

        setBehaviors(behaviorsList);
        hasFetchedRef.current = true;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to fetch behaviors'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchBehaviors();
  }, [sessionToken, refreshKey, sessionStatus]);

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

    const tagsClient = new TagsClient(sessionToken);

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

      const behaviorClient = new BehaviorClient(sessionToken);
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

        const createdWithMetrics = await behaviorClient.getBehaviorWithMetrics(
          created.id
        );

        setBehaviors(prev => [...prev, createdWithMetrics]);

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
        const updated = await behaviorClient.updateBehavior(editingId, {
          name: name.trim(),
          description: description?.trim() || null,
        });

        try {
          await syncBehaviorTags(editingId, existing?.tags ?? [], tagNames);
        } catch {
          tagSyncFailed = true;
        }

        const refreshed =
          await behaviorClient.getBehaviorWithMetrics(editingId);

        setBehaviors(prev =>
          prev.map(b =>
            b.id === editingId
              ? {
                  ...b,
                  name: updated.name,
                  description: updated.description,
                  tags: refreshed.tags ?? [],
                }
              : b
          )
        );

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

      const behaviorClient = new BehaviorClient(sessionToken);

      const created = await behaviorClient.createBehavior({
        name: generateCopyName(name),
        description: description || null,
        organization_id: organizationId,
      });

      const createdWithMetrics = await behaviorClient.getBehaviorWithMetrics(
        created.id
      );

      setBehaviors(prev => [...prev, createdWithMetrics]);

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
        const behaviorClient = new BehaviorClient(sessionToken);

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

        setBehaviors(prev => prev.filter(b => b.id !== editingBehavior.id));

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

  /** Unique tag names across all loaded behaviors. Reused for drawer
   *  suggestions and filter chips so users group across behaviors. */
  const availableTagNames = React.useMemo(
    () =>
      Array.from(
        new Set(behaviors.flatMap(b => (b.tags ?? []).map(t => t.name)))
      ).sort((a, b) => a.localeCompare(b)),
    [behaviors]
  );

  const filteredBehaviors = React.useMemo(() => {
    let filtered = behaviors;

    if (metricCountFilter !== 'all') {
      filtered = filtered.filter(behavior => {
        const hasMetrics = behavior.metrics && behavior.metrics.length > 0;
        if (metricCountFilter === 'has_metrics') return hasMetrics;
        if (metricCountFilter === 'no_metrics') return !hasMetrics;
        return true;
      });
    }

    if (drawerFilters.tagNames.length > 0) {
      const selected = new Set(drawerFilters.tagNames);
      filtered = filtered.filter(behavior =>
        (behavior.tags ?? []).some(t => selected.has(t.name))
      );
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(behavior => {
        const nameMatch = behavior.name.toLowerCase().includes(query);
        const descriptionMatch = behavior.description
          ?.toLowerCase()
          .includes(query);
        const metricMatch = behavior.metrics?.some(
          metric =>
            metric.name?.toLowerCase().includes(query) ||
            metric.description?.toLowerCase().includes(query)
        );
        const tagMatch = (behavior.tags ?? []).some(t =>
          t.name?.toLowerCase().includes(query)
        );
        return nameMatch || descriptionMatch || metricMatch || tagMatch;
      });
    }

    return filtered;
  }, [behaviors, searchQuery, metricCountFilter, drawerFilters]);

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

  // Loading state
  if (isLoading) {
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
  if (!sessionToken) {
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

  return (
    <PageLayout
      title="Behaviors"
      description="Behaviors are atomic expectations for your application, measured through one or more metrics to determine if requirements are met."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<AddIcon />}
            tooltip="Create behavior"
            aria-label="Create behavior"
            onClick={handleAddNewBehavior}
          />
        </FabGroup>
      }
    >
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search behaviors…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveBehaviorFilters(drawerFilters)}
        sx={directoryToolbarSx}
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

      {/* Behaviors grid / empty states */}
      {filteredBehaviors.length === 0 ? (
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
            icon={PsychologyIcon}
            title="No behavior yet"
            description="Create your first behavior to define atomic expectations for your AI applications. Behaviors are measured through metrics to ensure your requirements are met."
            actionLabel="Create behavior"
            onAction={handleAddNewBehavior}
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
          {filteredBehaviors
            .sort((a, b) => a.name.localeCompare(b.name))
            .map(behavior => (
              <BehaviorCard
                key={behavior.id}
                behavior={behavior}
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
                sessionToken={sessionToken}
              />
            ))}
        </Box>
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
        sessionToken={sessionToken}
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
