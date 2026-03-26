'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/AddOutlined';
import DownloadIcon from '@mui/icons-material/FileDownloadOutlined';
import EditIcon from '@mui/icons-material/Edit';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteIcon from '@mui/icons-material/Delete';
import ButtonGroup from '@mui/material/ButtonGroup';
import TablePagination from '@mui/material/TablePagination';
import CodeIcon from '@mui/icons-material/Code';
import ListIcon from '@mui/icons-material/List';
import { useRouter, useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import SearchAndFilterBar from '@/components/common/SearchAndFilterBar';
import SelectBehaviorsDialog from '@/components/common/SelectBehaviorsDialog';
import FilterDrawer, {
  FilterSection as DrawerFilterSection,
  FilterValues,
} from '@/components/common/FilterDrawer';
import PageHeader from '@/components/layout/PageHeader';
import FloatingActionButton from '@/components/common/FloatingActionButton';
import MetricCard from './MetricCard';
import MetricTypeDialog from './MetricTypeDialog';
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
import { generateCopyName } from '@/utils/entity-helpers';

interface FilterState {
  search: string;
  backend: string[];
  type: string[];
  scoreType: string[];
  metricScope: string[];
  behavior: string[];
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
  const [createMetricOpen, setCreateMetricOpen] = React.useState(false);
  const [deleteMetricDialogOpen, setDeleteMetricDialogOpen] =
    React.useState(false);
  const [metricToDeleteCompletely, setMetricToDeleteCompletely] =
    React.useState<{ id: string; name: string } | null>(null);
  const [isDeletingMetric, setIsDeletingMetric] = React.useState(false);

  // Pagination state
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(25);

  // Filter drawer state
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

  // Count active advanced filters (everything except search and backend which are in the toolbar)
  const activeAdvancedFilterCount =
    filters.type.length +
    filters.scoreType.length +
    filters.metricScope.length +
    filters.behavior.length;

  // Build FilterDrawer sections from filterOptions
  const drawerSections: DrawerFilterSection[] = React.useMemo(() => {
    const sections: DrawerFilterSection[] = [
      {
        id: 'scoreType',
        title: 'Score Type',
        type: 'checkbox',
        options: filterOptions.scoreType.map(o => ({
          value: o.value,
          label: o.label,
        })),
      },
      {
        id: 'metricScope',
        title: 'Metric Scope',
        type: 'checkbox',
        options: filterOptions.metricScope.map(o => ({
          value: o.value,
          label: o.label,
        })),
      },
    ];

    if (filterOptions.type.length > 0) {
      sections.push({
        id: 'type',
        title: 'Metric Type',
        type: 'checkbox',
        options: filterOptions.type.map(o => ({
          value: o.type_value,
          label: o.type_value
            .replace(/-/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' '),
        })),
      });
    }

    if (filterOptions.behavior.length > 0) {
      sections.push({
        id: 'behavior',
        title: 'Behaviors',
        type: 'checkbox',
        options: filterOptions.behavior.map(o => ({
          value: o.id,
          label: o.name,
        })),
        showAllThreshold: 5,
      });
    }

    return sections;
  }, [filterOptions]);

  // Build current filter values for the drawer
  const drawerValues: FilterValues = React.useMemo(
    () => ({
      scoreType: filters.scoreType,
      type: filters.type,
      metricScope: filters.metricScope,
      behavior: filters.behavior,
    }),
    [filters.scoreType, filters.type, filters.metricScope, filters.behavior]
  );

  const handleDrawerApply = (values: FilterValues) => {
    setFilters(prev => ({
      ...prev,
      scoreType: values.scoreType || [],
      type: values.type || [],
      metricScope: values.metricScope || [],
      behavior: values.behavior || [],
    }));
    setPage(0);
  };

  const handleDrawerReset = () => {
    setFilters(prev => ({
      ...prev,
      type: [],
      scoreType: [],
      metricScope: [],
      behavior: [],
    }));
    setPage(0);
  };

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

      // Behavior filter
      const behaviors = metric.behaviors;
      const behaviorMatch =
        !filters.behavior ||
        filters.behavior.length === 0 ||
        (behaviors &&
          Array.isArray(behaviors) &&
          behaviors.length > 0 &&
          filters.behavior.some(behaviorId => {
            // Check if behaviors is an array of strings (UUIDs) or BehaviorReference objects
            if (typeof behaviors[0] === 'string') {
              return (behaviors as string[]).includes(behaviorId);
            } else {
              return behaviors.some(
                (b: { id?: string }) => b.id === behaviorId
              );
            }
          }));

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

  // Function to check if any filter is active
  const hasActiveFilters = () => {
    return (
      filters.search !== '' ||
      filters.backend.length > 0 ||
      filters.type.length > 0 ||
      filters.scoreType.length > 0 ||
      filters.metricScope.length > 0 ||
      filters.behavior.length > 0
    );
  };

  // Function to reset all filters
  const handleResetFilters = () => {
    setFilters({
      search: '',
      backend: [],
      type: [],
      scoreType: [],
      metricScope: [],
      behavior: [],
    });
    setPage(0);
  };

  const handleMetricDetail = (metricType: string) => {
    router.push(`/metrics/${metricType}`);
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

  const handleDuplicateMetric = async (metric: MetricDetail) => {
    if (!sessionToken) return;

    try {
      const metricClient = new MetricsClient(sessionToken);

      const created = await metricClient.createMetric({
        name: generateCopyName(metric.name),
        description: metric.description || undefined,
        tags: metric.tags?.map(t => t.name) || [],
        evaluation_prompt: metric.evaluation_prompt || '',
        evaluation_steps: metric.evaluation_steps || undefined,
        evaluation_examples: metric.evaluation_examples || undefined,
        reasoning: metric.reasoning || undefined,
        score_type: metric.score_type || 'numeric',
        min_score: metric.min_score,
        max_score: metric.max_score,
        categories: metric.categories,
        passing_categories: metric.passing_categories,
        threshold: metric.threshold,
        threshold_operator: metric.threshold_operator,
        explanation: metric.explanation || '',
        ground_truth_required: metric.ground_truth_required,
        metric_scope: metric.metric_scope,
        metric_type_id: metric.metric_type?.id as UUID,
        backend_type_id: metric.backend_type?.id as UUID,
        model_id: metric.model_id,
      });

      // Fetch the created metric with full details
      const createdDetail = await metricClient.getMetric(created.id);
      setMetrics(prev => [createdDetail as MetricDetail, ...prev]);

      notifications.show('Metric duplicated successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to duplicate metric', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
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
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <>
      <PageHeader
        title="Metrics"
        description="Metrics are quantifiable measurements that evaluate behaviors and determine if requirements are met."
        actions={
          <>
            <FloatingActionButton
              icon={<DownloadIcon />}
              tooltip="Export metrics"
            />
            <FloatingActionButton
              icon={<AddIcon />}
              tooltip="New metric"
              onClick={() => setCreateMetricOpen(true)}
            />
          </>
        }
      />

      <Box sx={{ px: 4, pb: 4, pt: 3 }}>
        <SearchAndFilterBar
          searchValue={filters.search}
          onSearchChange={value => handleFilterChange('search', value)}
          onReset={hasActiveFilters() ? handleResetFilters : undefined}
          hasActiveFilters={hasActiveFilters()}
          searchPlaceholder="Search metrics..."
          onFilterClick={() => setFilterDrawerOpen(true)}
          activeFilterCount={activeAdvancedFilterCount}
        >
          {/* Backend Filter */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => handleFilterChange('backend', [])}
              variant={filters.backend.length === 0 ? 'contained' : 'outlined'}
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            {filterOptions.backend.map(option => {
              const isSelected = filters.backend.includes(
                option.type_value.toLowerCase()
              );
              return (
                <Button
                  key={option.type_value}
                  onClick={() => {
                    const value = option.type_value.toLowerCase();
                    const newBackend = isSelected
                      ? filters.backend.filter(b => b !== value)
                      : [...filters.backend, value];
                    handleFilterChange('backend', newBackend);
                  }}
                  variant={isSelected ? 'contained' : 'outlined'}
                  startIcon={<CodeIcon fontSize="small" />}
                >
                  {option.type_value}
                </Button>
              );
            })}
          </ButtonGroup>
        </SearchAndFilterBar>

        <FilterDrawer
          open={filterDrawerOpen}
          onClose={() => setFilterDrawerOpen(false)}
          sections={drawerSections}
          values={drawerValues}
          onApply={handleDrawerApply}
          onReset={handleDrawerReset}
        />

        {/* Metrics grid */}
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
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 8,
                      right: 8,
                      display: 'flex',
                      gap: 1,
                      zIndex: 1,
                    }}
                  >
                    {/* Only show detail button for rhesis and custom metrics */}
                    {(metric.backend_type?.type_value?.toLowerCase() ===
                      'rhesis' ||
                      metric.backend_type?.type_value?.toLowerCase() ===
                        'custom') && (
                      <IconButton
                        size="small"
                        onClick={e => {
                          if (assignMode) e.stopPropagation();
                          handleMetricDetail(metric.id);
                        }}
                        sx={{
                          padding: theme.spacing(0.25),
                          '& .MuiSvgIcon-root': {
                            fontSize:
                              theme?.typography?.helperText?.fontSize ||
                              '0.75rem',
                          },
                        }}
                      >
                        <EditIcon fontSize="inherit" />
                      </IconButton>
                    )}
                    <IconButton
                      size="small"
                      onClick={e => {
                        if (assignMode) e.stopPropagation();
                        setSelectedMetric(metric);
                        setAssignDialogOpen(true);
                      }}
                      sx={{
                        padding: theme => theme.spacing(0.25),
                        '& .MuiSvgIcon-root': {
                          fontSize:
                            theme?.typography?.helperText?.fontSize ||
                            '0.75rem',
                        },
                      }}
                    >
                      <AddIcon fontSize="inherit" />
                    </IconButton>
                    {/* Duplicate button for rhesis and custom metrics */}
                    {(metric.backend_type?.type_value?.toLowerCase() ===
                      'rhesis' ||
                      metric.backend_type?.type_value?.toLowerCase() ===
                        'custom') && (
                      <IconButton
                        size="small"
                        onClick={e => {
                          e.stopPropagation();
                          handleDuplicateMetric(metric);
                        }}
                        sx={{
                          padding: theme.spacing(0.25),
                          '& .MuiSvgIcon-root': {
                            fontSize:
                              theme?.typography?.helperText?.fontSize ||
                              '0.75rem',
                          },
                        }}
                      >
                        <ContentCopyIcon fontSize="inherit" />
                      </IconButton>
                    )}
                    {/* Only show delete button for unassigned custom metrics */}
                    {assignedBehaviors.length === 0 &&
                      metric.backend_type?.type_value?.toLowerCase() ===
                        'custom' && (
                        <IconButton
                          size="small"
                          onClick={e => {
                            e.stopPropagation();
                            handleDeleteMetric(metric.id, metric.name);
                          }}
                          sx={{
                            padding: theme.spacing(0.25),
                            '& .MuiSvgIcon-root': {
                              fontSize:
                                theme?.typography?.helperText?.fontSize ||
                                '0.75rem',
                            },
                          }}
                        >
                          <DeleteIcon fontSize="inherit" />
                        </IconButton>
                      )}
                  </Box>
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
        <MetricTypeDialog
          open={createMetricOpen}
          onClose={() => setCreateMetricOpen(false)}
        />
      </Box>
    </>
  );
}
