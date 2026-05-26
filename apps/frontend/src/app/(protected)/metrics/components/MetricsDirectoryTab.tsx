'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import TablePagination from '@mui/material/TablePagination';
import GridToolbar, {
  PrimarySegmentedPills,
  directoryToolbarSx,
} from '@/components/common/GridToolbar';
import { useRouter, useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import SelectBehaviorsDialog from '@/components/common/SelectBehaviorsDialog';
import MetricFilterDrawer from './MetricFilterDrawer';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import MetricCard from './MetricCard';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import {
  MetricDetail,
  MetricScope,
} from '@/utils/api-client/interfaces/metric';
import type {
  Behavior as ApiBehavior,
  BehaviorWithMetrics,
} from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';
export interface FilterState {
  search: string;
  backend: string[];
  type: string[];
  scoreType: string[];
  metricScope: string[];
  behavior: string;
}

interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
  behavior: { id: string; name: string }[];
}

interface BehaviorMetrics {
  [behaviorId: string]: {
    metrics: MetricDetail[];
    isLoading: boolean;
    error: string | null;
  };
}

// Using SelectBehaviorsDialog component instead of inline dialog

interface MetricsDirectoryTabProps {
  sessionToken: string;
  organizationId: UUID;
  behaviors: ApiBehavior[];
  metrics: MetricDetail[];
  filters: FilterState;
  filterOptions: FilterOptions;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  setMetrics: React.Dispatch<React.SetStateAction<MetricDetail[]>>;
  setBehaviorMetrics: React.Dispatch<React.SetStateAction<BehaviorMetrics>>;
  setBehaviorsWithMetrics: React.Dispatch<
    React.SetStateAction<BehaviorWithMetrics[]>
  >;
  assignMode?: boolean; // Whether we're in assign mode (coming from behaviors page)
}

// Add type guard function
function isValidMetricType(
  type: string | undefined
): type is 'custom-prompt' | 'api-call' | 'custom-code' | 'grading' {
  return (
    type === 'custom-prompt' ||
    type === 'api-call' ||
    type === 'custom-code' ||
    type === 'grading'
  );
}

export default function MetricsDirectoryTab({
  sessionToken,
  organizationId: _organizationId,
  behaviors,
  metrics,
  filters,
  filterOptions,
  isLoading,
  error,
  onRefresh: _onRefresh,
  setFilters,
  setMetrics,
  setBehaviorMetrics,
  setBehaviorsWithMetrics,
  assignMode = false,
}: MetricsDirectoryTabProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const theme = useTheme();

  // Dialog state
  const [assignDialogOpen, setAssignDialogOpen] = React.useState(false);
  const [selectedMetric, setSelectedMetric] =
    React.useState<MetricDetail | null>(null);
  const [fabAnchorEl, setFabAnchorEl] = React.useState<null | HTMLElement>(
    null
  );
  const fabMenuOpen = Boolean(fabAnchorEl);
  const [deleteMetricDialogOpen, setDeleteMetricDialogOpen] =
    React.useState(false);
  const [metricToDeleteCompletely, setMetricToDeleteCompletely] =
    React.useState<{ id: string; name: string } | null>(null);
  const [isDeletingMetric, setIsDeletingMetric] = React.useState(false);

  // Pagination state
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(25);

  // Advanced filters drawer state
  const [filterDrawerOpen, setFilterDrawerOpen] = React.useState(false);

  // Filter handlers
  const handleFilterChange = (
    filterType: keyof FilterState,
    value: string | string[]
  ) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value,
    }));
    setPage(0);
  };

  // Count active advanced filters
  const behaviorStr =
    typeof filters.behavior === 'string' ? filters.behavior : '';
  const activeAdvancedFilterCount =
    filters.type.length +
    filters.scoreType.length +
    filters.metricScope.length +
    (behaviorStr.trim() !== '' ? 1 : 0);

  // Filter metrics based on search and filter criteria
  const getFilteredMetrics = () => {
    return metrics.filter(metric => {
      // Search filter
      const searchMatch =
        !filters.search ||
        (metric.name || '')
          .toLowerCase()
          .includes(filters.search.toLowerCase()) ||
        (metric.description || '')
          .toLowerCase()
          .includes(filters.search.toLowerCase()) ||
        (metric.metric_type?.type_value || '')
          .toLowerCase()
          .includes(filters.search.toLowerCase());

      // Backend filter
      const backendMatch =
        filters.backend.length === 0 ||
        (metric.backend_type &&
          filters.backend.includes(
            metric.backend_type.type_value.toLowerCase()
          ));

      // Type filter
      const typeMatch =
        filters.type.length === 0 ||
        (metric.metric_type?.type_value &&
          filters.type.includes(metric.metric_type.type_value));

      // Score type filter
      const scoreTypeMatch =
        !filters.scoreType ||
        filters.scoreType.length === 0 ||
        (metric.score_type && filters.scoreType.includes(metric.score_type));

      // Metric scope filter
      const metricScopeMatch =
        !filters.metricScope ||
        filters.metricScope.length === 0 ||
        (metric.metric_scope &&
          filters.metricScope.some(scope =>
            metric.metric_scope?.includes(scope as MetricScope)
          ));

      // Behavior filter — text match against assigned behavior names
      const behaviorFilter =
        typeof filters.behavior === 'string' ? filters.behavior : '';
      const metricBehaviorIds = Array.isArray(metric.behaviors)
        ? metric.behaviors.map((b: string | { id?: string }) =>
            typeof b === 'string' ? b : b.id
          )
        : [];
      const metricBehaviorNames = behaviors
        .filter(b => metricBehaviorIds.includes(b.id as string))
        .map(b => b.name || '');
      const behaviorMatch =
        behaviorFilter.trim() === '' ||
        metricBehaviorNames.some(
          name => name.toLowerCase() === behaviorFilter.toLowerCase()
        );

      return (
        searchMatch &&
        backendMatch &&
        typeMatch &&
        scoreTypeMatch &&
        metricScopeMatch &&
        behaviorMatch
      );
    });
  };

  // Function to assign a metric to a behavior
  const handleAssignMetricToBehavior = async (
    behaviorId: string,
    metricId: string
  ) => {
    try {
      const metricClient = new MetricsClient(sessionToken);

      // Assign metric to behavior
      await metricClient.addBehaviorToMetric(
        metricId as UUID,
        behaviorId as UUID
      );

      // Update local state optimistically - add behavior to metric's behaviors list
      setMetrics(prevMetrics =>
        prevMetrics.map(metric => {
          if (metric.id === metricId) {
            const currentBehaviors = Array.isArray(metric.behaviors)
              ? metric.behaviors
              : [];
            // Add behavior ID if not already present
            const behaviorIds = currentBehaviors.map(b =>
              typeof b === 'string' ? b : b.id
            );
            if (!behaviorIds.includes(behaviorId)) {
              // Maintain consistent type - if current behaviors are strings, add string; if objects, add object
              const isStringArray =
                currentBehaviors.length === 0 ||
                typeof currentBehaviors[0] === 'string';
              const newBehavior = isStringArray
                ? behaviorId
                : { id: behaviorId as UUID, name: '', description: '' };
              return {
                ...metric,
                behaviors: [
                  ...currentBehaviors,
                  newBehavior,
                ] as MetricDetail['behaviors'],
              };
            }
          }
          return metric;
        })
      );

      // Find the metric to add to behavior's metrics
      const targetMetric = metrics.find(m => m.id === metricId);
      if (targetMetric) {
        // Update behaviorMetrics state
        setBehaviorMetrics(prev => ({
          ...prev,
          [behaviorId]: {
            ...prev[behaviorId],
            metrics: [...(prev[behaviorId]?.metrics || []), targetMetric],
            isLoading: false,
            error: null,
          },
        }));

        // Update behaviorsWithMetrics state
        setBehaviorsWithMetrics(prevBehaviors =>
          prevBehaviors.map(behavior =>
            behavior.id === behaviorId
              ? {
                  ...behavior,
                  metrics: [
                    ...(behavior.metrics || []),
                    targetMetric as MetricDetail,
                  ],
                }
              : behavior
          )
        );
      }

      notifications.show('Successfully assigned metric to behavior', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to assign metric to behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  // Function to remove a metric from a behavior
  const _handleRemoveMetricFromBehavior = async (
    behaviorId: string,
    metricId: string
  ) => {
    try {
      const metricClient = new MetricsClient(sessionToken);

      // Remove metric from behavior
      await metricClient.removeBehaviorFromMetric(
        metricId as UUID,
        behaviorId as UUID
      );

      // Update local state optimistically - remove behavior from metric's behaviors list
      setMetrics(prevMetrics =>
        prevMetrics.map(metric => {
          if (metric.id === metricId) {
            const currentBehaviors = Array.isArray(metric.behaviors)
              ? metric.behaviors
              : [];
            return {
              ...metric,
              behaviors: currentBehaviors.filter(b => {
                const behaviorId_str = typeof b === 'string' ? b : b.id;
                return behaviorId_str !== behaviorId;
              }) as MetricDetail['behaviors'],
            };
          }
          return metric;
        })
      );

      // Update behaviorMetrics state - remove the metric
      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: {
          ...prev[behaviorId],
          metrics: (prev[behaviorId]?.metrics || []).filter(
            m => m.id !== metricId
          ),
          isLoading: false,
          error: null,
        },
      }));

      // Update behaviorsWithMetrics state - remove the metric
      setBehaviorsWithMetrics(prevBehaviors =>
        prevBehaviors.map(behavior =>
          behavior.id === behaviorId
            ? {
                ...behavior,
                metrics: (behavior.metrics || []).filter(
                  m => m.id !== metricId
                ),
              }
            : behavior
        )
      );

      notifications.show('Successfully removed metric from behavior', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  const handleAssignMetric = (behaviorId: UUID) => {
    if (selectedMetric) {
      handleAssignMetricToBehavior(behaviorId as string, selectedMetric.id);
    }
    setAssignDialogOpen(false);
    setSelectedMetric(null);

    // Clear assignMode param from URL if present
    if (assignMode) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('assignMode');
      router.replace(`/metrics?${params.toString()}`, { scroll: false });
    }
  };

  // Function to delete a metric
  const handleDeleteMetric = async (metricId: string, metricName: string) => {
    setMetricToDeleteCompletely({ id: metricId, name: metricName });
    setDeleteMetricDialogOpen(true);
  };

  const handleConfirmDeleteMetric = async () => {
    if (!sessionToken || !metricToDeleteCompletely) return;

    try {
      setIsDeletingMetric(true);
      const metricClient = new MetricsClient(sessionToken);
      await metricClient.deleteMetric(metricToDeleteCompletely.id as UUID);

      // Remove the metric from local state
      setMetrics(prevMetrics =>
        prevMetrics.filter(m => m.id !== metricToDeleteCompletely.id)
      );

      notifications.show('Metric deleted successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to delete metric', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeletingMetric(false);
      setDeleteMetricDialogOpen(false);
      setMetricToDeleteCompletely(null);
    }
  };

  const handleCancelDeleteMetric = () => {
    setDeleteMetricDialogOpen(false);
    setMetricToDeleteCompletely(null);
  };

  const filteredMetrics = getFilteredMetrics();
  const activeBehaviors = behaviors.filter(b => b.name && b.name.trim() !== '');

  // Clamp page when list shrinks (e.g. after delete/duplicate)
  React.useEffect(() => {
    const lastPage = Math.max(
      0,
      Math.ceil(filteredMetrics.length / rowsPerPage) - 1
    );
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [filteredMetrics.length, rowsPerPage, page]);

  if (isLoading) {
    return (
      <PageLayout title="Metrics" breadcrumbs={[]}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            p: 4,
            minHeight: theme => theme.spacing(50),
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={24} />
            <Typography>Loading metrics directory...</Typography>
          </Box>
        </Box>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title="Metrics" breadcrumbs={[]}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <Typography color="error">{error}</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Metrics"
      description="Metrics are quantifiable measurements that evaluate behaviors and determine if requirements are met."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<AddIcon />}
            tooltip="Create metric"
            aria-label="Create metric"
            onClick={e => setFabAnchorEl(e.currentTarget)}
          />
          <Menu
            anchorEl={fabAnchorEl}
            open={fabMenuOpen}
            onClose={() => setFabAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem
              onClick={() => {
                setFabAnchorEl(null);
                router.push('/metrics/new?type=custom-prompt');
              }}
            >
              LLM judge
            </MenuItem>
            <MenuItem
              onClick={() => {
                setFabAnchorEl(null);
                router.push('/metrics/new?type=custom-code');
              }}
            >
              Code Evaluation
            </MenuItem>
          </Menu>
        </FabGroup>
      }
    >
      <GridToolbar
        searchQuery={filters.search}
        onSearchChange={value => handleFilterChange('search', value)}
        searchPlaceholder="Search metrics..."
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={activeAdvancedFilterCount > 0}
        sx={directoryToolbarSx}
        middleContent={
          <PrimarySegmentedPills
            mode="multi"
            tabs={[
              { value: '', label: 'All' },
              ...filterOptions.backend.map(o => ({
                value: o.type_value.toLowerCase(),
                label: o.type_value,
              })),
            ]}
            selectedValues={filters.backend}
            onMultiChange={values => handleFilterChange('backend', values)}
            clearValue=""
          />
        }
      />

      {/* Advanced Filters Drawer */}
      <MetricFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={{
          type: filters.type,
          scoreType: filters.scoreType,
          metricScope: filters.metricScope,
          behavior:
            typeof filters.behavior === 'string' ? filters.behavior : '',
        }}
        filterOptions={{
          type: filterOptions.type,
          scoreType: filterOptions.scoreType,
          metricScope: filterOptions.metricScope,
          behavior: filterOptions.behavior,
        }}
        onApply={drawerFilters => {
          setFilters(prev => ({
            ...prev,
            type: drawerFilters.type,
            scoreType: drawerFilters.scoreType,
            metricScope: drawerFilters.metricScope,
            behavior: drawerFilters.behavior,
          }));
          setPage(0);
        }}
      />

      {/* Metrics grid */}
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
        {filteredMetrics
          .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
          .map(metric => {
            const assignedBehaviors = activeBehaviors.filter(b => {
              if (!Array.isArray(metric.behaviors)) return false;
              // Check if behaviors is an array of strings (UUIDs) or BehaviorReference objects
              const behaviorIds = metric.behaviors.map(behavior =>
                typeof behavior === 'string' ? behavior : behavior.id
              );
              return behaviorIds.includes(b.id as string);
            });
            const behaviorNames = assignedBehaviors.map(
              b => b.name || 'Unnamed Behavior'
            );

            return (
              <Box
                key={metric.id}
                sx={{
                  position: 'relative',
                  ...(assignMode && {
                    cursor: 'pointer',
                    transition: theme.transitions.create(
                      ['transform', 'box-shadow'],
                      {
                        duration: theme.transitions.duration.short,
                      }
                    ),
                    '&:hover': {
                      transform: `translateY(-${theme.spacing(0.5)})`,
                    },
                    '&:active': {
                      transform: `translateY(-${theme.spacing(0.25)})`,
                    },
                  }),
                }}
                onClick={
                  assignMode
                    ? () => {
                        setSelectedMetric(metric);
                        setAssignDialogOpen(true);
                      }
                    : undefined
                }
              >
                <MetricCard
                  type={
                    isValidMetricType(metric.metric_type?.type_value)
                      ? metric.metric_type.type_value
                      : undefined
                  }
                  title={metric.name}
                  description={metric.description}
                  backend={metric.backend_type?.type_value}
                  metricType={metric.metric_type?.type_value}
                  scoreType={metric.score_type}
                  metricScope={metric.metric_scope}
                  usedIn={behaviorNames}
                  showUsage={true}
                  onDelete={
                    assignedBehaviors.length === 0 &&
                    metric.backend_type?.type_value?.toLowerCase() === 'custom'
                      ? () => handleDeleteMetric(metric.id, metric.name)
                      : undefined
                  }
                />
              </Box>
            );
          })}
      </Box>
      {filteredMetrics.length > 0 && (
        <TablePagination
          component="div"
          count={filteredMetrics.length}
          page={page}
          onPageChange={(_event, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={event => {
            setRowsPerPage(parseInt(event.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100]}
          labelRowsPerPage="Metrics per page:"
          sx={{ mb: 2 }}
        />
      )}
      {/* Dialogs */}
      <DeleteModal
        open={deleteMetricDialogOpen}
        onClose={handleCancelDeleteMetric}
        onConfirm={handleConfirmDeleteMetric}
        isLoading={isDeletingMetric}
        itemType="metric"
        itemName={metricToDeleteCompletely?.name}
      />
      <SelectBehaviorsDialog
        open={assignDialogOpen}
        onClose={() => {
          setAssignDialogOpen(false);
          setSelectedMetric(null);
        }}
        onSelect={handleAssignMetric}
        sessionToken={sessionToken}
        excludeBehaviorIds={(selectedMetric?.behaviors || [])
          .filter(b => typeof b !== 'string' && b.id)
          .map(b => (typeof b !== 'string' ? b.id : (b as unknown as UUID)))}
      />
    </PageLayout>
  );
}
