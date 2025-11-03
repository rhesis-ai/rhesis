'use client';

import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Chip from '@mui/material/Chip';
import SearchIcon from '@mui/icons-material/Search';
import InputAdornment from '@mui/material/InputAdornment';
import Stack from '@mui/material/Stack';
import CircularProgress from '@mui/material/CircularProgress';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DeleteIcon from '@mui/icons-material/Delete';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import { useRouter, useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import MetricCard from './MetricCard';
import MetricTypeDialog from './MetricTypeDialog';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
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
}

interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
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
  onTabChange: () => void; // Function to switch to Selected Metrics tab
  assignMode?: boolean; // Whether we're in assign mode (coming from "Add New Behavior")
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
  onTabChange,
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

      return searchMatch && backendMatch && typeMatch && scoreTypeMatch;
    });
  };

  // Function to check if any filter is active
  const hasActiveFilters = () => {
    return (
      filters.search !== '' ||
      filters.backend.length > 0 ||
      filters.type.length > 0 ||
      filters.scoreType.length > 0
    );
  };

  // Function to reset all filters
  const handleResetFilters = () => {
    setFilters({
      search: '',
      backend: [],
      type: [],
      scoreType: [],
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
          minHeight: '400px',
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
      sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}
    >
      {/* Search and Filters */}
      <Box sx={{ p: 3, bgcolor: 'background.paper' }}>
        <Stack spacing={3}>
          {/* Header with Search and Create */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            <TextField
              fullWidth
              placeholder="Search metrics..."
              value={filters.search}
              onChange={e => handleFilterChange('search', e.target.value)}
              variant="filled"
              hiddenLabel
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateMetricOpen(true)}
              sx={{
                whiteSpace: 'nowrap',
                minWidth: 'auto',
              }}
            >
              New Metric
            </Button>
            {hasActiveFilters() && (
              <Button
                variant="outlined"
                startIcon={<ClearIcon />}
                onClick={handleResetFilters}
                sx={{ whiteSpace: 'nowrap' }}
              >
                Reset
              </Button>
            )}
          </Box>

          {/* Filter Groups */}
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {/* Backend Filter */}
            <FormControl sx={{ minWidth: 200, flex: 1 }} size="small">
              <InputLabel id="backend-filter-label">Backend</InputLabel>
              <Select
                labelId="backend-filter-label"
                id="backend-filter"
                multiple
                value={filters.backend}
                onChange={e =>
                  handleFilterChange('backend', e.target.value as string[])
                }
                label="Backend"
                renderValue={selected => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.length === 0 ? (
                      <em>Select backend</em>
                    ) : (
                      selected.map(value => (
                        <Chip key={value} label={value} size="small" />
                      ))
                    )}
                  </Box>
                )}
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 224,
                      width: 250,
                    },
                  },
                }}
              >
                <MenuItem disabled value="">
                  <em>Select backend</em>
                </MenuItem>
                {filterOptions.backend.map(option => (
                  <MenuItem
                    key={option.type_value}
                    value={option.type_value.toLowerCase()}
                  >
                    {option.type_value}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Metric Type Filter */}
            <FormControl sx={{ minWidth: 200, flex: 1 }} size="small">
              <InputLabel id="type-filter-label">Metric Type</InputLabel>
              <Select
                labelId="type-filter-label"
                id="type-filter"
                multiple
                value={filters.type}
                onChange={e =>
                  handleFilterChange('type', e.target.value as string[])
                }
                label="Metric Type"
                renderValue={selected => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.length === 0 ? (
                      <em>Select metric type</em>
                    ) : (
                      selected.map(value => (
                        <Chip
                          key={value}
                          label={value
                            .replace(/-/g, ' ')
                            .split(' ')
                            .map(
                              word =>
                                word.charAt(0).toUpperCase() + word.slice(1)
                            )
                            .join(' ')}
                          size="small"
                        />
                      ))
                    )}
                  </Box>
                )}
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 224,
                      width: 250,
                    },
                  },
                }}
              >
                <MenuItem disabled value="">
                  <em>Select metric type</em>
                </MenuItem>
                {filterOptions.type.map(option => (
                  <MenuItem key={option.type_value} value={option.type_value}>
                    <Box>
                      <Typography>
                        {option.type_value
                          .replace(/-/g, ' ')
                          .split(' ')
                          .map(
                            word => word.charAt(0).toUpperCase() + word.slice(1)
                          )
                          .join(' ')}
                      </Typography>
                      {option.description && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                        >
                          {option.description}
                        </Typography>
                      )}
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Score Type Filter */}
            <FormControl sx={{ minWidth: 200, flex: 1 }} size="small">
              <InputLabel id="score-type-filter-label">Score Type</InputLabel>
              <Select
                labelId="score-type-filter-label"
                id="score-type-filter"
                multiple
                value={filters.scoreType}
                onChange={e =>
                  handleFilterChange('scoreType', e.target.value as string[])
                }
                label="Score Type"
                renderValue={selected => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.length === 0 ? (
                      <em>Select score type</em>
                    ) : (
                      selected.map(value => (
                        <Chip
                          key={value}
                          label={
                            filterOptions.scoreType.find(
                              opt => opt.value === value
                            )?.label || value
                          }
                          size="small"
                        />
                      ))
                    )}
                  </Box>
                )}
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 224,
                      width: 250,
                    },
                  },
                }}
              >
                <MenuItem disabled value="">
                  <em>Select score type</em>
                </MenuItem>
                {filterOptions.scoreType.map(option => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Stack>
      </Box>

      {/* Metrics Stack */}
      <Box sx={{ p: 3, flex: 1, overflow: 'auto' }}>
        <Stack
          spacing={3}
          sx={{
            '& > *': {
              display: 'flex',
              flexDirection: 'row',
              flexWrap: 'wrap',
              gap: 3,
              '& > *': {
                flex: {
                  xs: '1 1 100%',
                  sm: '1 1 calc(50% - 12px)',
                  md: '1 1 calc(33.333% - 16px)',
                },
                minWidth: { xs: '100%', sm: '300px', md: '320px' },
                maxWidth: {
                  xs: '100%',
                  sm: 'calc(50% - 12px)',
                  md: 'calc(33.333% - 16px)',
                },
              },
            },
          }}
        >
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
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
                    flex: {
                      xs: '1 1 100%',
                      sm: '1 1 calc(50% - 12px)',
                      md: '1 1 calc(33.333% - 16px)',
                    },
                    minWidth: { xs: '100%', sm: '300px', md: '320px' },
                    maxWidth: {
                      xs: '100%',
                      sm: 'calc(50% - 12px)',
                      md: 'calc(33.333% - 16px)',
                    },
                    ...(assignMode && {
                      cursor: 'pointer',
                      transition:
                        'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                      },
                      '&:active': {
                        transform: 'translateY(-2px)',
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
                    <IconButton
                      size="small"
                      onClick={e => {
                        if (assignMode) e.stopPropagation();
                        handleMetricDetail(metric.id);
                      }}
                      sx={{
                        padding: '2px',
                        '& .MuiSvgIcon-root': {
                          fontSize:
                            theme?.typography?.helperText?.fontSize ||
                            '0.75rem',
                        },
                      }}
                    >
                      <OpenInNewIcon fontSize="inherit" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={e => {
                        if (assignMode) e.stopPropagation();
                        setSelectedMetric(metric);
                        setAssignDialogOpen(true);
                      }}
                      sx={{
                        padding: '2px',
                        '& .MuiSvgIcon-root': {
                          fontSize:
                            theme?.typography?.helperText?.fontSize ||
                            '0.75rem',
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
                            padding: '2px',
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
                    usedIn={behaviorNames}
                    showUsage={true}
                  />
                </Box>
              );
            })}
          </Box>
        </Stack>
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
