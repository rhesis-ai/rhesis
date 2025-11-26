'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import AddIcon from '@mui/icons-material/Add';
import ListIcon from '@mui/icons-material/List';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ClearIcon from '@mui/icons-material/Clear';
import { useNotifications } from '@/components/common/NotificationContext';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';
import BehaviorCard from './BehaviorCard';
import BehaviorDrawer from './BehaviorDrawer';
import BehaviorMetricsViewer from './BehaviorMetricsViewer';
import SearchAndFilterBar from '@/components/common/SearchAndFilterBar';

interface BehaviorsClientProps {
  sessionToken: string;
  organizationId: UUID;
}

export default function BehaviorsClient({
  sessionToken,
  organizationId,
}: BehaviorsClientProps) {
  const notifications = useNotifications();
  const theme = useTheme();

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

  // Search state
  const [searchQuery, setSearchQuery] = React.useState('');

  // Filter state
  const [metricCountFilter, setMetricCountFilter] = React.useState<
    'all' | 'has_metrics' | 'no_metrics'
  >('all');

  // Refresh key for manual refresh
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Use ref to track the actual session token value to prevent unnecessary re-fetches
  const lastSessionTokenRef = React.useRef<string | null>(null);
  const hasFetchedRef = React.useRef(false);

  // Fetch behaviors
  React.useEffect(() => {
    const fetchBehaviors = async () => {
      if (!sessionToken) {
        setIsLoading(false);
        return;
      }

      // Check if session token changed
      if (
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
  }, [sessionToken, refreshKey]);

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
        // Create new behavior
        const created = await behaviorClient.createBehavior({
          name,
          description: description || null,
          organization_id: organizationId,
        });

        // Fetch the created behavior with metrics
        const createdWithMetrics = await behaviorClient.getBehaviorWithMetrics(
          created.id
        );

        setBehaviors(prev => [...prev, createdWithMetrics]);

        notifications.show('Behavior created successfully', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } else if (editingBehavior && editingBehavior.id) {
        // Update existing behavior
        const updated = await behaviorClient.updateBehavior(
          editingBehavior.id,
          {
            name,
            description: description || null,
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

  const handleDeleteBehavior = async () => {
    if (!isNewBehavior && editingBehavior && editingBehavior.id) {
      try {
        const behaviorClient = new BehaviorClient(sessionToken);

        // Check if behavior has metrics
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

  const handleMetricsViewerRefresh = () => {
    handleRefresh();
    // Also update the viewing behavior with fresh data
    if (viewingBehavior) {
      const updatedBehavior = behaviors.find(b => b.id === viewingBehavior.id);
      if (updatedBehavior) {
        setViewingBehavior(updatedBehavior);
      }
    }
  };

  // Filter behaviors based on search and metric count
  const filteredBehaviors = React.useMemo(() => {
    let filtered = behaviors;

    // Apply metric count filter
    if (metricCountFilter !== 'all') {
      filtered = filtered.filter(behavior => {
        const hasMetrics = behavior.metrics && behavior.metrics.length > 0;
        if (metricCountFilter === 'has_metrics') {
          return hasMetrics;
        } else if (metricCountFilter === 'no_metrics') {
          return !hasMetrics;
        }
        return true;
      });
    }

    // Apply search filter
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
  }, [behaviors, searchQuery, metricCountFilter]);

  const handleResetFilters = () => {
    setSearchQuery('');
    setMetricCountFilter('all');
  };

  const hasActiveFilters =
    searchQuery.trim() !== '' || metricCountFilter !== 'all';

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 4,
          minHeight: theme => theme.spacing(25),
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={24} />
          <Typography>Loading behaviors...</Typography>
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      {/* Header with explanation */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body1" color="text.secondary">
          Behaviors are atomic expectations for your application, measured
          through one or more metrics to determine if requirements are met.
        </Typography>
      </Box>

      {/* Search and Filter Bar */}
      <SearchAndFilterBar
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        onAddNew={handleAddNewBehavior}
        addNewLabel="New Behavior"
        searchPlaceholder="Search behaviors..."
      >
        {/* Metric Count Filter */}
        <ButtonGroup size="small" variant="outlined">
          <Button
            onClick={() => setMetricCountFilter('all')}
            variant={metricCountFilter === 'all' ? 'contained' : 'outlined'}
            startIcon={<ListIcon fontSize="small" />}
          >
            All
          </Button>
          <Button
            onClick={() => setMetricCountFilter('has_metrics')}
            variant={
              metricCountFilter === 'has_metrics' ? 'contained' : 'outlined'
            }
            startIcon={<CheckCircleIcon fontSize="small" />}
            sx={{
              ...(metricCountFilter === 'has_metrics' && {
                backgroundColor: theme.palette.success.main,
                '&:hover': {
                  backgroundColor: theme.palette.success.dark,
                },
              }),
            }}
          >
            Has Metrics
          </Button>
          <Button
            onClick={() => setMetricCountFilter('no_metrics')}
            variant={
              metricCountFilter === 'no_metrics' ? 'contained' : 'outlined'
            }
            startIcon={<ErrorOutlineIcon fontSize="small" />}
            sx={{
              ...(metricCountFilter === 'no_metrics' && {
                backgroundColor: theme.palette.warning.main,
                '&:hover': {
                  backgroundColor: theme.palette.warning.dark,
                },
              }),
            }}
          >
            No Metrics
          </Button>
        </ButtonGroup>

        {/* Reset Button - inline with filters */}
        {hasActiveFilters && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<ClearIcon />}
            onClick={handleResetFilters}
            sx={{ whiteSpace: 'nowrap' }}
          >
            Reset
          </Button>
        )}
      </SearchAndFilterBar>

      {/* Behaviors grid */}
      {filteredBehaviors.length > 0 ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'repeat(2, 1fr)',
              lg: 'repeat(3, 1fr)',
            },
            gap: 3,
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
                onViewMetrics={() => handleViewMetrics(behavior)}
                onRefresh={handleRefresh}
                sessionToken={sessionToken}
              />
            ))}
        </Box>
      ) : behaviors.length > 0 ? (
        <Box
          sx={{
            p: 4,
            textAlign: 'center',
            border: theme => `2px dashed ${theme.palette.divider}`,
            borderRadius: 2,
          }}
        >
          <Typography variant="body1" color="text.secondary">
            No behaviors match your search criteria.
          </Typography>
        </Box>
      ) : (
        <Box
          sx={{
            p: 4,
            textAlign: 'center',
            border: theme => `2px dashed ${theme.palette.divider}`,
            borderRadius: 2,
          }}
        >
          <Typography variant="body1" color="text.secondary" gutterBottom>
            No behaviors found. Create your first behavior to get started.
          </Typography>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleAddNewBehavior}
            sx={{ mt: 2 }}
          >
            Add New Behavior
          </Button>
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
          onDelete={
            !isNewBehavior &&
            editingBehavior.id &&
            behaviors.find(b => b.id === editingBehavior.id)?.metrics.length ===
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
    </Box>
  );
}
