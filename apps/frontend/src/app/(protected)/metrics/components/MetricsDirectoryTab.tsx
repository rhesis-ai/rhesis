'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DeleteIcon from '@mui/icons-material/Delete';
import ButtonGroup from '@mui/material/ButtonGroup';
import Badge from '@mui/material/Badge';
import Popover from '@mui/material/Popover';
import Divider from '@mui/material/Divider';
import FormGroup from '@mui/material/FormGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import FilterListIcon from '@mui/icons-material/FilterList';
import CodeIcon from '@mui/icons-material/Code';
import FunctionsIcon from '@mui/icons-material/Functions';
import CategoryIcon from '@mui/icons-material/Category';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import ListIcon from '@mui/icons-material/List';
import TuneIcon from '@mui/icons-material/Tune';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import { useRouter, useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import SearchAndFilterBar from '@/components/common/SearchAndFilterBar';
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
    metrics: MetricDetail[] | any[];
    isLoading: boolean;
    error: string | null;
  };
}

interface AssignMetricDialogProps {
  open: boolean;
  onClose: () => void;
  onAssign: (behaviorId: string) => void;
  behaviors: ApiBehavior[];
  isLoading: boolean;
  error: string | null;
}

function AssignMetricDialog({
  open,
  onClose,
  onAssign,
  behaviors,
  isLoading,
  error,
}: AssignMetricDialogProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Add to Behavior</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Select a behavior to add this metric to:
        </DialogContentText>
        {isLoading ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
              }}
            >
              <CircularProgress size={20} />
              <Typography>Loading behaviors...</Typography>
            </Box>
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : behaviors.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="text.secondary">
              No behaviors available
            </Typography>
          </Box>
        ) : (
          <Stack spacing={2} sx={{ mt: 2 }}>
            {[...behaviors]
              .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
              .map(behavior => (
                <Button
                  key={behavior.id}
                  variant="outlined"
                  onClick={() => onAssign(behavior.id)}
                  fullWidth
                >
                  {behavior.name || 'Unnamed Behavior'}
                </Button>
              ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}

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
  organizationId,
  behaviors,
  metrics,
  filters,
  filterOptions,
  isLoading,
  error,
  onRefresh,
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
  
  // Advanced filters popover state
  const [anchorEl, setAnchorEl] = React.useState<HTMLButtonElement | null>(null);

  // Filter handlers
  const handleFilterChange = (
    filterType: keyof FilterState,
    value: string | string[]
  ) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value,
    }));
  };

  // Popover handlers
  const handleFilterClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleFilterClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  // Count active advanced filters
  const activeAdvancedFilterCount =
    filters.type.length +
    filters.scoreType.length +
    filters.metricScope.length +
    filters.behavior.length;

  const handleClearAllAdvancedFilters = () => {
    setFilters(prev => ({
      ...prev,
      type: [],
      scoreType: [],
      metricScope: [],
      behavior: [],
    }));
  };

  // Filter metrics based on search and filter criteria
  const getFilteredMetrics = () => {
    return metrics.filter(metric => {
      // Search filter
      const searchMatch =
        !filters.search ||
        metric.name.toLowerCase().includes(filters.search.toLowerCase()) ||
        metric.description
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
      const behaviorMatch =
        !filters.behavior ||
        filters.behavior.length === 0 ||
        (metric.behaviors &&
          Array.isArray(metric.behaviors) &&
          metric.behaviors.length > 0 &&
          filters.behavior.some(behaviorId => {
            // Check if behaviors is an array of strings (UUIDs) or BehaviorReference objects
            if (typeof metric.behaviors![0] === 'string') {
              return (metric.behaviors as string[]).includes(behaviorId);
            } else {
              return metric.behaviors!.some(
                (b: any) => b.id === behaviorId
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
                  metrics: [...(behavior.metrics || []), targetMetric as any],
                }
              : behavior
          )
        );
      }

      notifications.show('Successfully assigned metric to behavior', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (err) {
      notifications.show('Failed to assign metric to behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  // Function to remove a metric from a behavior
  const handleRemoveMetricFromBehavior = async (
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
    } catch (err) {
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  const handleAssignMetric = (behaviorId: string) => {
    if (selectedMetric) {
      handleAssignMetricToBehavior(behaviorId, selectedMetric.id);
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
    } catch (err) {
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
    <Box
      sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      {/* Explanation */}
      <Box sx={{ px: 3, pt: 2, pb: 2 }}>
        <Typography variant="body1" color="text.secondary">
        Metrics are quantifiable measurements that evaluate behaviors and determine if requirements are met.
          </Typography>
      </Box>

      {/* Search and Filters */}
      <Box sx={{ px: 3 }}>
        <SearchAndFilterBar
        searchValue={filters.search}
        onSearchChange={(value) => handleFilterChange('search', value)}
        onReset={hasActiveFilters() ? handleResetFilters : undefined}
        hasActiveFilters={hasActiveFilters()}
        onAddNew={() => setCreateMetricOpen(true)}
        addNewLabel="New Metric"
        searchPlaceholder="Search metrics..."
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
            const isSelected = filters.backend.includes(option.type_value.toLowerCase());
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

        {/* More Filters Toggle */}
        <Badge 
          badgeContent={activeAdvancedFilterCount}
          color="primary"
          invisible={activeAdvancedFilterCount === 0}
        >
          <Button
            size="small"
            variant="outlined"
            startIcon={<FilterListIcon />}
            onClick={handleFilterClick}
          >
            Filters
          </Button>
        </Badge>
        </SearchAndFilterBar>

        {/* Advanced Filters Popover */}
        <Popover
          open={open}
          anchorEl={anchorEl}
          onClose={handleFilterClose}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'left',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'left',
          }}
          PaperProps={{
            sx: {
              p: 0,
              width: 400,
              maxHeight: 600,
            },
          }}
        >
          {/* Header */}
          <Box
            sx={{
              p: 2,
              borderBottom: 1,
              borderColor: 'divider',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              Advanced Filters
            </Typography>
            {activeAdvancedFilterCount > 0 && (
              <Button
                size="small"
                startIcon={<ClearAllIcon />}
                onClick={handleClearAllAdvancedFilters}
                color="secondary"
              >
                Clear All
              </Button>
            )}
          </Box>

          {/* Content */}
          <Box sx={{ p: 2.5, maxHeight: 520, overflow: 'auto' }}>
            <Stack spacing={3}>
              {/* Score Type */}
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                  <FunctionsIcon fontSize="small" color="action" />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Score Type
                  </Typography>
                </Box>
                <FormGroup>
                  {filterOptions.scoreType.map(option => (
                    <FormControlLabel
                      key={option.value}
                      control={
                        <Checkbox
                          checked={filters.scoreType.includes(option.value)}
                          onChange={(e) => {
                            const newScoreType = e.target.checked
                              ? [...filters.scoreType, option.value]
                              : filters.scoreType.filter(s => s !== option.value);
                            handleFilterChange('scoreType', newScoreType);
                          }}
                          size="small"
                        />
                      }
                      label={option.label}
                    />
                  ))}
                </FormGroup>
              </Box>

              <Divider />

              {/* Metric Type */}
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                  <TuneIcon fontSize="small" color="action" />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Metric Type
                  </Typography>
                </Box>
                <FormGroup>
                  {filterOptions.type.map(option => (
                    <FormControlLabel
                      key={option.type_value}
                      control={
                        <Checkbox
                          checked={filters.type.includes(option.type_value)}
                          onChange={(e) => {
                            const newType = e.target.checked
                              ? [...filters.type, option.type_value]
                              : filters.type.filter(t => t !== option.type_value);
                            handleFilterChange('type', newType);
                          }}
                          size="small"
                        />
                      }
                      label={option.type_value
                        .replace(/-/g, ' ')
                        .split(' ')
                        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                        .join(' ')}
                    />
                  ))}
                </FormGroup>
              </Box>

              <Divider />

              {/* Metric Scope */}
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                  <CategoryIcon fontSize="small" color="action" />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Metric Scope
                  </Typography>
                </Box>
                <FormGroup>
                  {filterOptions.metricScope.map(option => (
                    <FormControlLabel
                      key={option.value}
                      control={
                        <Checkbox
                          checked={filters.metricScope.includes(option.value)}
                          onChange={(e) => {
                            const newScope = e.target.checked
                              ? [...filters.metricScope, option.value]
                              : filters.metricScope.filter(s => s !== option.value);
                            handleFilterChange('metricScope', newScope);
                          }}
                          size="small"
                        />
                      }
                      label={option.label}
                    />
                  ))}
                </FormGroup>
              </Box>

              {filterOptions.behavior.length > 0 && (
                <>
                  <Divider />

                  {/* Behaviors */}
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                      <AccountTreeIcon fontSize="small" color="action" />
                      <Typography variant="subtitle2" fontWeight={600}>
                        Behaviors
                      </Typography>
                    </Box>
                    <FormGroup>
                      {filterOptions.behavior.map(option => (
                        <FormControlLabel
                          key={option.id}
                          control={
                            <Checkbox
                              checked={filters.behavior.includes(option.id)}
                              onChange={(e) => {
                                const newBehavior = e.target.checked
                                  ? [...filters.behavior, option.id]
                                  : filters.behavior.filter(b => b !== option.id);
                                handleFilterChange('behavior', newBehavior);
                              }}
                              size="small"
                            />
                          }
                          label={option.name}
                        />
                      ))}
                    </FormGroup>
                  </Box>
                </>
              )}
            </Stack>
          </Box>
        </Popover>
      </Box>
      
      {/* Metrics Stack */}
      <Box
        sx={{
          p: 3,
          flex: 1,
          overflow: 'auto',
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(3, 1fr)',
          },
          gap: 3,
        }}
      >
        {filteredMetrics.map(metric => {
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
                    <OpenInNewIcon fontSize="inherit" />
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
                        theme?.typography?.helperText?.fontSize || '0.75rem',
                    },
                  }}
                >
                  <AddIcon fontSize="inherit" />
                </IconButton>
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
      {/* Dialogs */}
      <DeleteModal
        open={deleteMetricDialogOpen}
        onClose={handleCancelDeleteMetric}
        onConfirm={handleConfirmDeleteMetric}
        isLoading={isDeletingMetric}
        itemType="metric"
        itemName={metricToDeleteCompletely?.name}
      />
      <AssignMetricDialog
        open={assignDialogOpen}
        onClose={() => {
          setAssignDialogOpen(false);
          setSelectedMetric(null);
        }}
        onAssign={handleAssignMetric}
        behaviors={behaviors.filter(b => b.name && b.name.trim() !== '')}
        isLoading={isLoading}
        error={error}
      />
      <MetricTypeDialog
        open={createMetricOpen}
        onClose={() => setCreateMetricOpen(false)}
      />
    </Box>
  );
}
