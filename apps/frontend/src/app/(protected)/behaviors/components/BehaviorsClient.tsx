'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Paper from '@mui/material/Paper';
import AddIcon from '@mui/icons-material/Add';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarSx,
} from '@/components/common/GridToolbar';
import { useNotifications } from '@/components/common/NotificationContext';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
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
import { BORDER_RADIUS, ELEVATION, GREYSCALE } from '@/styles/theme';

interface EmptyStateMessageProps {
  title: string;
  description: string;
}

function EmptyStateMessage({ title, description }: EmptyStateMessageProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 4,
        textAlign: 'center',
        borderRadius: BORDER_RADIUS.md,
        border: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        boxShadow: ELEVATION.xs,
      }}
    >
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {description}
      </Typography>
    </Paper>
  );
}

interface BehaviorsClientProps {
  sessionToken: string;
  organizationId: UUID;
  sessionStatus?: 'loading' | 'authenticated' | 'unauthenticated';
}

export default function BehaviorsClient({
  sessionToken,
  organizationId,
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
    setEditingBehavior({ id: null, name: '', description: '' });
    setIsNewBehavior(true);
    setDrawerOpen(true);
  };

  const handleEditBehavior = (id: UUID, name: string, description: string) => {
    setEditingBehavior({ id, name, description });
    setIsNewBehavior(false);
    setDrawerOpen(true);
  };

  const handleSaveBehavior = async (name: string, description: string) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);

      const behaviorClient = new BehaviorClient(sessionToken);

      if (isNewBehavior) {
        const created = await behaviorClient.createBehavior({
          name: name.trim(),
          description: description?.trim() || null,
          organization_id: organizationId,
        });

        const createdWithMetrics = await behaviorClient.getBehaviorWithMetrics(
          created.id
        );

        setBehaviors(prev => [...prev, createdWithMetrics]);

        notifications.show('Behavior created successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } else if (editingBehavior && editingBehavior.id) {
        const updated = await behaviorClient.updateBehavior(
          editingBehavior.id,
          {
            name: name.trim(),
            description: description?.trim() || null,
          }
        );

        setBehaviors(prev =>
          prev.map(b =>
            b.id === editingBehavior.id
              ? { ...b, name: updated.name, description: updated.description }
              : b
          )
        );

        notifications.show('Behavior updated successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
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
        return nameMatch || descriptionMatch || metricMatch;
      });
    }

    return filtered;
  }, [behaviors, searchQuery, metricCountFilter, drawerFilters]);

  const hasActiveFilters =
    searchQuery.trim() !== '' || metricCountFilter !== 'all';
  const editingBehaviorId = !isNewBehavior ? editingBehavior?.id : null;

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
        <EmptyStateMessage
          title="Authentication Required"
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
          <EmptyStateMessage
            title="No behaviors match your filters"
            description="Try adjusting your search or filter to find the behaviors you're looking for."
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
                    behavior.description || ''
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
        onApply={f => {
          setDrawerFilters(f);
          setMetricCountFilter(f.metricCount);
        }}
      />
    </PageLayout>
  );
}
