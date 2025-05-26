'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import { useSession } from 'next-auth/react';
import ChecklistIcon from '@mui/icons-material/Checklist';
import ViewQuiltIcon from '@mui/icons-material/ViewQuilt';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import MetricCard from './components/MetricCard';
import SectionEditDrawer from './components/DimensionDrawer';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DeleteIcon from '@mui/icons-material/Delete';
import { useRouter } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Chip from '@mui/material/Chip';
import SearchIcon from '@mui/icons-material/Search';
import InputAdornment from '@mui/material/InputAdornment';
import Stack from '@mui/material/Stack';
import ClearIcon from '@mui/icons-material/Clear';
import { PageContainer } from '@toolpad/core/PageContainer';
import MetricTypeDialog from './components/MetricTypeDialog';
import { TypeLookupClient } from '@/utils/api-client/type-lookup-client';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { Behavior as ApiBehavior } from '@/utils/api-client/interfaces/behavior';
import type { Status } from '@/utils/api-client/interfaces/status';
import type { User } from '@/utils/api-client/interfaces/user';
import type { TypeLookup as MetricType } from '@/utils/api-client/interfaces/type-lookup';
import type { TypeLookup as BackendType } from '@/utils/api-client/interfaces/type-lookup';
import type { UUID } from 'crypto';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function CustomTabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`metrics-tabpanel-${index}`}
      aria-labelledby={`metrics-tab-${index}`}
      {...other}
      style={{ height: '100%' }}
    >
      {value === index && (
        <Box sx={{ height: '100%' }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `metrics-tab-${index}`,
    'aria-controls': `metrics-tabpanel-${index}`,
  };
}

interface Organization {
  id: string;
  name: string;
  description: string;
  email: string;
}

interface Metric {
  id: string;
  name: string;
  description: string;
  evaluation_prompt: string;
  evaluation_steps: string;
  reasoning: string;
  score_type: string;
  min_score: number;
  max_score: number;
  threshold: number;
  explanation: string;
  metric_type: MetricType;
  backend_type: BackendType | null;
  status: Status | null;
  owner: User;
  organization: Organization;
  behavior_id?: string;
}

interface Behavior {
  id: string;
  name: string;
  description: string | null;
  status: Status;
  organization: Organization;
  user: User | null;
}

interface MetricSectionItem {
  type: 'answer_relevancy' | 'faithfulness' | 'contextual_relevancy' | 'contextual_precision' | 'contextual_recall';
  title: string;
  description: string;
  backend: string;
  defaultThreshold: number;
  requiresGroundTruth: boolean;
  metricType: 'Grading' | 'API Call' | 'Custom Code' | 'Custom Prompt';
}

interface MetricSections {
  [key: string]: MetricSectionItem[];
}

interface FilterState {
  search: string;
  backend: string[];
  type: string[];
  scoreType: string[];
}

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: []
};

interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
}

const initialFilterOptions: FilterOptions = {
  backend: [],
  type: [],
  scoreType: [
    { value: 'binary', label: 'Binary (Pass/Fail)' },
    { value: 'numeric', label: 'Numeric' }
  ]
};

interface AssignMetricDialogProps {
  open: boolean;
  onClose: () => void;
  onAssign: (behaviorId: string) => void;
  behaviors: ApiBehavior[];
  isLoading: boolean;
  error: string | null;
}

function AssignMetricDialog({ open, onClose, onAssign, behaviors, isLoading, error }: AssignMetricDialogProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Add to Behavior</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Select a behavior to add this metric to:
        </DialogContentText>
        {isLoading ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography>Loading behaviors...</Typography>
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : behaviors.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="text.secondary">No behaviors available</Typography>
          </Box>
        ) : (
          <Stack spacing={2} sx={{ mt: 2 }}>
            {behaviors.map((behavior) => (
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

interface BehaviorMetrics {
  [behaviorId: string]: {
    metrics: MetricDetail[];
    isLoading: boolean;
    error: string | null;
  }
}

interface LocalMetricType {
  type_value: string;
}

// Add type guard function
function isValidMetricType(type: string | undefined): type is 'custom-prompt' | 'api-call' | 'custom-code' | 'grading' {
  return type === 'custom-prompt' || type === 'api-call' || type === 'custom-code' || type === 'grading';
}

export default function MetricsPage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const notifications = useNotifications();
  const [value, setValue] = React.useState(0);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [metricToDelete, setMetricToDelete] = React.useState<{ sectionKey: string; index: number; title: string } | null>(null);
  const [editingSection, setEditingSection] = React.useState<{
    key: UUID | null;
    title: string;
    description: string;
  } | null>(null);
  const [isNewSection, setIsNewSection] = React.useState(false);
  const [behaviors, setBehaviors] = React.useState<ApiBehavior[]>([]);
  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [sections, setSections] = React.useState<MetricSections>({});
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);
  const [filterOptions, setFilterOptions] = React.useState<FilterOptions>(initialFilterOptions);
  const [assignDialogOpen, setAssignDialogOpen] = React.useState(false);
  const [selectedMetric, setSelectedMetric] = React.useState<MetricDetail | null>(null);
  const [createMetricOpen, setCreateMetricOpen] = React.useState(false);
  const [behaviorMetrics, setBehaviorMetrics] = React.useState<BehaviorMetrics>({});
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string>();
  const [deleteMetricDialogOpen, setDeleteMetricDialogOpen] = React.useState(false);
  const [metricToDeleteCompletely, setMetricToDeleteCompletely] = React.useState<{ id: string; name: string } | null>(null);
  const initialDataLoadedRef = React.useRef(false);

  // Fetch behaviors, metrics, and filter options
  React.useEffect(() => {
    const fetchData = async () => {
      // Skip if data has already been loaded
      if (initialDataLoadedRef.current) return;
      
      try {
        setIsLoading(true);
        setError(null);

        const typeLookupClient = new TypeLookupClient(session?.session_token);
        const behaviorClient = new BehaviorClient(session?.session_token);
        const metricClient = new MetricsClient(session?.session_token);

        const [behaviorsData, metricsData, typeLookupData] = await Promise.all([
          behaviorClient.getBehaviors({
            skip: 0,
            sort_by: 'created_at',
            sort_order: 'desc'
          }),
          metricClient.getMetrics({
            skip: 0,
            limit: 100,
            sortBy: 'created_at',
            sortOrder: 'desc'
          }),
          typeLookupClient.getTypeLookups({
            skip: 0,
            limit: 100,
            sort_by: 'created_at',
            sort_order: 'asc'
          })
        ]);

        // Fetch behaviors for each metric
        const metricsWithBehaviors = await Promise.all(
          (metricsData.data || []).map(async (metric) => {
            try {
              const metricBehaviors = await metricClient.getMetricBehaviors(metric.id as UUID);
              return {
                ...metric,
                behaviors: metricBehaviors.data?.map(b => b.id) || []
              };
            } catch (err) {
              console.error(`Error fetching behaviors for metric ${metric.id}:`, err);
              return metric;
            }
          })
        );

        setBehaviors(behaviorsData);
        setMetrics(metricsWithBehaviors);

        // Initialize behavior metrics state
        const initialBehaviorMetrics: BehaviorMetrics = {};
        behaviorsData.forEach(behavior => {
          initialBehaviorMetrics[behavior.id] = {
            metrics: [],
            isLoading: true,
            error: null
          };
        });
        setBehaviorMetrics(initialBehaviorMetrics);

        // Fetch metrics for each behavior
        const behaviorMetricsPromises = behaviorsData.map(async behavior => {
          try {
            const behaviorMetricsList = await behaviorClient.getBehaviorMetrics(behavior.id as UUID);
            return {
              behaviorId: behavior.id,
              metrics: behaviorMetricsList,
              error: null
            };
          } catch (err) {
            console.error(`Error fetching metrics for behavior ${behavior.id}:`, err);
            return {
              behaviorId: behavior.id,
              metrics: [],
              error: err instanceof Error ? err.message : 'Failed to load metrics'
            };
          }
        });

        // Update behavior metrics as they complete
        const behaviorMetricsResults = await Promise.all(behaviorMetricsPromises);
        const updatedBehaviorMetrics = { ...initialBehaviorMetrics };
        behaviorMetricsResults.forEach(result => {
          updatedBehaviorMetrics[result.behaviorId] = {
            metrics: result.metrics,
            isLoading: false,
            error: result.error
          };
        });
        setBehaviorMetrics(updatedBehaviorMetrics);
        
        // Filter and set backend types and metric types
        const backendTypes = typeLookupData
          .filter((type: any) => type.type_name === 'BackendType')
          .map((type: any) => ({
            type_value: type.type_value.charAt(0).toUpperCase() + type.type_value.slice(1)
          }));

        const metricTypes = typeLookupData
          .filter((type: any) => type.type_name === 'MetricType')
          .map((type: any) => ({
            type_value: type.type_value,
            description: type.description || ''
          }));

        setFilterOptions(prev => ({
          ...prev,
          backend: backendTypes,
          type: metricTypes
        }));

        initialDataLoadedRef.current = true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
        notifications.show('Failed to load metrics data', {
          severity: 'error',
          autoHideDuration: 4000
        });
      } finally {
        setIsLoading(false);
      }
    };

    if (session?.session_token && !initialDataLoadedRef.current) {
      fetchData();
    }
  }, [session?.session_token, notifications]);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  const handleEditSection = (key: UUID, title: string, description: string) => {
    setEditingSection({ key, title, description });
    setIsNewSection(false);
    setDrawerOpen(true);
  };

  const handleAddNewSection = () => {
    setEditingSection({ key: null, title: '', description: '' });
    setIsNewSection(true);
    setDrawerOpen(true);
  };

  const handleSaveSection = async (title: string, description: string, organization_id: UUID) => {
    try {
      setDrawerLoading(true);
      setDrawerError(undefined);
      
      const behaviorClient = new BehaviorClient(session?.session_token);

      if (isNewSection) {
        // Create new behavior
        const createPayload = {
          name: title,
          description: description || null,
          organization_id
        };

        const created = await behaviorClient.createBehavior(createPayload);
        
        // Batch state updates
        const newBehaviors = [...behaviors, created];
        const newBehaviorMetrics = {
          ...behaviorMetrics,
          [created.id]: { metrics: [], isLoading: false, error: null }
        };
        
        setBehaviors(newBehaviors);
        setBehaviorMetrics(newBehaviorMetrics);
        
        notifications.show('Dimension created successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
      } else if (editingSection && editingSection.key) {
        // Update existing behavior
        const updatePayload = {
          name: title,
          description: description || null,
          organization_id
        };

        const updated = await behaviorClient.updateBehavior(editingSection.key, updatePayload);
        setBehaviors(prev => prev.map(b => 
          b.id === editingSection.key 
            ? { ...b, name: updated.name, description: updated.description } 
            : b
        ));
        
        notifications.show('Dimension updated successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
      }
      setDrawerOpen(false);
    } catch (err) {
      console.error('Error saving behavior:', err);
      setDrawerError(err instanceof Error ? err.message : 'Failed to save dimension');
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDeleteSection = async () => {
    if (!isNewSection && editingSection && editingSection.key) {
      try {
        const behaviorClient = new BehaviorClient(session?.session_token);
        const metricsClient = new MetricsClient(session?.session_token);
        const behaviorData = behaviorMetrics[editingSection.key];

        if (behaviorData && behaviorData.metrics.length > 0) {
          // First remove all metrics from the behavior
          const removePromises = behaviorData.metrics.map(metric => 
            metricsClient.removeBehaviorFromMetric(metric.id as UUID, editingSection.key as UUID)
          );

          try {
            await Promise.all(removePromises);
          } catch (err) {
            console.error('Error removing metrics from behavior:', err);
            notifications.show(
              'Failed to remove all metrics from dimension. Please try again.',
              { severity: 'error', autoHideDuration: 4000 }
            );
            return;
          }
        }

        // Then delete the behavior itself
        await behaviorClient.deleteBehavior(editingSection.key);
        
        // Update local state
        setBehaviors(prev => prev.filter(b => b.id !== editingSection.key));
        setBehaviorMetrics(prev => {
          const newState = { ...prev };
          const key = editingSection?.key as UUID;
          if (key) {
            delete newState[key];
          }
          return newState;
        });
        
        notifications.show('Dimension deleted successfully', { 
          severity: 'success', 
          autoHideDuration: 4000 
        });
        setDrawerOpen(false);
      } catch (err) {
        console.error('Error deleting behavior:', err);
        notifications.show(
          err instanceof Error ? err.message : 'Failed to delete dimension', 
          { severity: 'error', autoHideDuration: 4000 }
        );
      }
    } else {
      setDrawerOpen(false);
    }
  };

  const handleRemoveMetric = (sectionKey: string, metricIndex: number, metricTitle: string) => {
    setMetricToDelete({ sectionKey, index: metricIndex, title: metricTitle });
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = () => {
    if (metricToDelete) {
      setSections(prevSections => ({
        ...prevSections,
        [metricToDelete.sectionKey]: prevSections[metricToDelete.sectionKey].filter((_, index) => index !== metricToDelete.index)
      }));
      notifications.show(`Successfully removed ${metricToDelete.title} metric`, {
        severity: 'success',
        autoHideDuration: 4000
      });
    }
    setDeleteDialogOpen(false);
    setMetricToDelete(null);
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setMetricToDelete(null);
  };

  const handleMetricDetail = (metricType: string) => {
    router.push(`/metrics/${metricType}`);
  };

  // Filter handlers
  const handleFilterChange = (filterType: keyof FilterState, value: string | string[]) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value
    }));
  };

  // Filter metrics based on search and filter criteria
  const getFilteredMetrics = () => {
    return metrics.filter(metric => {
      // Search filter
      const searchMatch = !filters.search || 
        metric.name.toLowerCase().includes(filters.search.toLowerCase()) ||
        metric.description.toLowerCase().includes(filters.search.toLowerCase()) ||
        (metric.metric_type?.type_value || '').toLowerCase().includes(filters.search.toLowerCase());

      // Backend filter
      const backendMatch = filters.backend.length === 0 || 
        (metric.backend_type && filters.backend.includes(metric.backend_type.type_value.toLowerCase()));

      // Type filter
      const typeMatch = filters.type.length === 0 ||
        (metric.metric_type?.type_value && filters.type.includes(metric.metric_type.type_value));

      // Score type filter
      const scoreTypeMatch = !filters.scoreType || filters.scoreType.length === 0 ||
        (metric.score_type && filters.scoreType.includes(metric.score_type));

      return searchMatch && backendMatch && typeMatch && scoreTypeMatch;
    });
  };

  // Function to check if a metric is used in any dimension
  const getMetricUsage = (metric: MetricSectionItem): string[] => {
    return Object.entries(sections)
      .filter(([_, sectionMetrics]) => 
        sectionMetrics.some(m => 
          m.type === metric.type && 
          m.title === metric.title
        )
      )
      .map(([key]) => key);
  };

  // Function to assign a metric to a behavior
  const handleAssignMetricToBehavior = async (behaviorId: string, metricId: string) => {
    try {
      const behaviorClient = new BehaviorClient(session?.session_token);
      const metricClient = new MetricsClient(session?.session_token);

      // Assign metric to behavior
      await metricClient.addBehaviorToMetric(metricId as UUID, behaviorId as UUID);

      // Fetch updated metrics for the behavior
      const updatedBehaviorMetrics = await behaviorClient.getBehaviorMetrics(behaviorId as UUID);

      // Fetch updated behaviors for the metric
      const updatedMetricBehaviors = await metricClient.getMetricBehaviors(metricId as UUID);

      // Update both metrics and behaviorMetrics state
      setMetrics(prevMetrics => 
        prevMetrics.map(metric => 
          metric.id === metricId 
            ? { 
                ...metric, 
                behaviors: updatedMetricBehaviors.data?.map(b => b.id) || []
              }
            : metric
        )
      );

      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: {
          ...prev[behaviorId],
          metrics: updatedBehaviorMetrics,
          isLoading: false,
          error: null
        }
      }));
      
      notifications.show('Successfully assigned metric to behavior', {
        severity: 'success',
        autoHideDuration: 4000
      });
    } catch (err) {
      console.error('Error assigning metric to behavior:', err);
      notifications.show('Failed to assign metric to behavior', {
        severity: 'error',
        autoHideDuration: 4000
      });
    }
  };

  // Function to remove a metric from a behavior
  const handleRemoveMetricFromBehavior = async (behaviorId: string, metricId: string) => {
    try {
      const behaviorClient = new BehaviorClient(session?.session_token);
      const metricClient = new MetricsClient(session?.session_token);

      // Remove metric from behavior
      await metricClient.removeBehaviorFromMetric(metricId as UUID, behaviorId as UUID);

      // Fetch updated metrics for the behavior
      const updatedBehaviorMetrics = await behaviorClient.getBehaviorMetrics(behaviorId as UUID);

      // Fetch updated behaviors for the metric
      const updatedMetricBehaviors = await metricClient.getMetricBehaviors(metricId as UUID);

      // Update both metrics and behaviorMetrics state
      setMetrics(prevMetrics => 
        prevMetrics.map(metric => 
          metric.id === metricId 
            ? { 
                ...metric, 
                behaviors: updatedMetricBehaviors.data?.map(b => b.id) || []
              }
            : metric
        )
      );

      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: {
          ...prev[behaviorId],
          metrics: updatedBehaviorMetrics,
          isLoading: false,
          error: null
        }
      }));
      
      notifications.show('Successfully removed metric from behavior', {
        severity: 'success',
        autoHideDuration: 4000
      });
    } catch (err) {
      console.error('Error removing metric from behavior:', err);
      notifications.show('Failed to remove metric from behavior', {
        severity: 'error',
        autoHideDuration: 4000
      });
    }
  };

  const handleAssignMetric = (behaviorId: string) => {
    if (selectedMetric) {
      handleAssignMetricToBehavior(behaviorId, selectedMetric.id);
    }
    setAssignDialogOpen(false);
    setSelectedMetric(null);
  };

  // Function to delete a metric
  const handleDeleteMetric = async (metricId: string, metricName: string) => {
    setMetricToDeleteCompletely({ id: metricId, name: metricName });
    setDeleteMetricDialogOpen(true);
  };

  const handleConfirmDeleteMetric = async () => {
    if (!session?.session_token || !metricToDeleteCompletely) return;

    try {
      const metricClient = new MetricsClient(session.session_token);
      await metricClient.deleteMetric(metricToDeleteCompletely.id as UUID);
      
      // Remove the metric from local state
      setMetrics(prevMetrics => prevMetrics.filter(m => m.id !== metricToDeleteCompletely.id));
      
      notifications.show('Metric deleted successfully', {
        severity: 'success',
        autoHideDuration: 4000
      });
    } catch (err) {
      console.error('Error deleting metric:', err);
      notifications.show('Failed to delete metric', {
        severity: 'error',
        autoHideDuration: 4000
      });
    } finally {
      setDeleteMetricDialogOpen(false);
      setMetricToDeleteCompletely(null);
    }
  };

  const handleCancelDeleteMetric = () => {
    setDeleteMetricDialogOpen(false);
    setMetricToDeleteCompletely(null);
  };

  // Function to check if any filter is active
  const hasActiveFilters = () => {
    return filters.search !== '' || 
           filters.backend.length > 0 || 
           filters.type.length > 0 ||
           filters.scoreType.length > 0;
  };

  // Function to reset all filters
  const handleResetFilters = () => {
    setFilters(initialFilterState);
  };

  // Handle loading state
  if (status === 'loading') {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Authentication required. Please log in.
        </Typography>
      </Box>
    );
  }

  const renderSection = (behavior: ApiBehavior) => {
    const behaviorData = behaviorMetrics[behavior.id];
    const metricsLoading = behaviorData?.isLoading ?? false;
    const metricsError = behaviorData?.error ?? null;
    const behaviorMetricsList = behaviorData?.metrics ?? [];

    return (
      <Box key={behavior.id} sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography 
            variant="h6" 
            component="h2" 
            sx={{ fontWeight: 'bold' }}
          >
            {behavior.name}
          </Typography>
          <IconButton 
            onClick={() => handleEditSection(behavior.id as UUID, behavior.name, behavior.description || '')}
            size="small"
          >
            <EditIcon />
          </IconButton>
        </Box>
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{ mb: 3 }}
        >
          {behavior.description || 'No description provided'}
        </Typography>
        
        {metricsLoading ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography>Loading metrics...</Typography>
          </Box>
        ) : metricsError ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography color="error">{metricsError}</Typography>
          </Box>
        ) : behaviorMetricsList.length > 0 ? (
          <Box 
            sx={{ 
              display: 'flex',
              flexWrap: 'wrap',
              gap: 3,
              '& > *': {
                flex: { 
                  xs: '1 1 100%', 
                  sm: '1 1 calc(50% - 12px)', 
                  md: '1 1 calc(33.333% - 16px)' 
                },
                minWidth: { xs: '100%', sm: '300px', md: '320px' },
                maxWidth: { xs: '100%', sm: 'calc(50% - 12px)', md: 'calc(33.333% - 16px)' }
              }
            }}
          >
            {behaviorMetricsList.map((metric) => (
              <Box key={metric.id} sx={{ position: 'relative' }}>
                <Box 
                  sx={{ 
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    gap: 1,
                    zIndex: 1
                  }}
                >
                  <IconButton
                    size="small"
                    onClick={() => handleMetricDetail(metric.id)}
                    sx={{
                      padding: '2px',
                      '& .MuiSvgIcon-root': {
                        fontSize: '0.875rem'
                      }
                    }}
                  >
                    <OpenInNewIcon fontSize="inherit" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveMetricFromBehavior(behavior.id, metric.id);
                    }}
                    sx={{
                      padding: '2px',
                      '& .MuiSvgIcon-root': {
                        fontSize: '0.875rem'
                      }
                    }}
                  >
                    <CloseIcon fontSize="inherit" />
                  </IconButton>
                </Box>
                <MetricCard 
                  type={isValidMetricType(metric.metric_type?.type_value) ? metric.metric_type.type_value : undefined}
                  title={metric.name}
                  description={metric.description}
                  backend={metric.backend_type?.type_value}
                  metricType={metric.metric_type?.type_value}
                  scoreType={metric.score_type}
                  usedIn={[behavior.name]}
                  showUsage={false}
                />
              </Box>
            ))}
          </Box>
        ) : (
          <Paper 
            sx={{ 
              p: 3, 
              textAlign: 'center',
              backgroundColor: 'action.hover',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2
            }}
          >
            <Typography color="text.secondary">
              No metrics assigned to this behavior
            </Typography>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => {
                setValue(1); // Switch to Metrics Directory tab
              }}
            >
              Add Metric
            </Button>
          </Paper>
        )}
      </Box>
    );
  };

  const renderMetricsDirectory = () => {
    const filteredMetrics = getFilteredMetrics();
    const activeBehaviors = behaviors.filter(b => b.name && b.name.trim() !== '');

    return (
      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Search and Filters */}
        <Box sx={{ p: 3, bgcolor: 'background.paper' }}>
          <Stack spacing={3}>
            {/* Header with Search and Create */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
              <TextField
                fullWidth
                placeholder="Search metrics..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
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
                  minWidth: 'auto'
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
                  onChange={(e) => handleFilterChange('backend', e.target.value as string[])}
                  label="Backend"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.length === 0 ? (
                        <em>Select backend</em>
                      ) : (
                        selected.map((value) => (
                          <Chip 
                            key={value} 
                            label={value} 
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
                        width: 250
                      }
                    }
                  }}
                >
                  <MenuItem disabled value="">
                    <em>Select backend</em>
                  </MenuItem>
                  {filterOptions.backend.map((option) => (
                    <MenuItem key={option.type_value} value={option.type_value.toLowerCase()}>
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
                  onChange={(e) => handleFilterChange('type', e.target.value as string[])}
                  label="Metric Type"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.length === 0 ? (
                        <em>Select metric type</em>
                      ) : (
                        selected.map((value) => (
                          <Chip 
                            key={value} 
                            label={value.replace(/-/g, ' ').split(' ').map(word => 
                              word.charAt(0).toUpperCase() + word.slice(1)
                            ).join(' ')} 
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
                        width: 250
                      }
                    }
                  }}
                >
                  <MenuItem disabled value="">
                    <em>Select metric type</em>
                  </MenuItem>
                  {filterOptions.type.map((option) => (
                    <MenuItem key={option.type_value} value={option.type_value}>
                      <Box>
                        <Typography>
                          {option.type_value.replace(/-/g, ' ').split(' ').map(word => 
                            word.charAt(0).toUpperCase() + word.slice(1)
                          ).join(' ')}
                        </Typography>
                        {option.description && (
                          <Typography variant="caption" color="text.secondary" display="block">
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
                  onChange={(e) => handleFilterChange('scoreType', e.target.value as string[])}
                  label="Score Type"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.length === 0 ? (
                        <em>Select score type</em>
                      ) : (
                        selected.map((value) => (
                          <Chip 
                            key={value} 
                            label={filterOptions.scoreType.find(opt => opt.value === value)?.label || value}
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
                        width: 250
                      }
                    }
                  }}
                >
                  <MenuItem disabled value="">
                    <em>Select score type</em>
                  </MenuItem>
                  {filterOptions.scoreType.map((option) => (
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
                  flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 12px)', md: '1 1 calc(33.333% - 16px)' },
                  minWidth: { xs: '100%', sm: '300px', md: '320px' },
                  maxWidth: { xs: '100%', sm: 'calc(50% - 12px)', md: 'calc(33.333% - 16px)' }
                }
              }
            }}
          >
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {filteredMetrics.map((metric) => {
                const assignedBehaviors = activeBehaviors.filter(b => metric.behaviors?.includes(b.id));
                const behaviorNames = assignedBehaviors.map(b => b.name || 'Unnamed Behavior');
                
                return (
                  <Box key={metric.id} sx={{ position: 'relative', flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 12px)', md: '1 1 calc(33.333% - 16px)' }, minWidth: { xs: '100%', sm: '300px', md: '320px' }, maxWidth: { xs: '100%', sm: 'calc(50% - 12px)', md: 'calc(33.333% - 16px)' } }}>
                    <Box 
                      sx={{ 
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        display: 'flex',
                        gap: 1,
                        zIndex: 1
                      }}
                    >
                      <IconButton
                        size="small"
                        onClick={() => handleMetricDetail(metric.id)}
                        sx={{
                          padding: '2px',
                          '& .MuiSvgIcon-root': {
                            fontSize: '0.875rem'
                          }
                        }}
                      >
                        <OpenInNewIcon fontSize="inherit" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => {
                          setSelectedMetric(metric);
                          setAssignDialogOpen(true);
                        }}
                        sx={{
                          padding: '2px',
                          '& .MuiSvgIcon-root': {
                            fontSize: '0.875rem'
                          }
                        }}
                      >
                        <AddIcon fontSize="inherit" />
                      </IconButton>
                      {assignedBehaviors.length > 0 ? (
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveMetricFromBehavior(assignedBehaviors[0].id, metric.id);
                          }}
                          sx={{
                            padding: '2px',
                            '& .MuiSvgIcon-root': {
                              fontSize: '0.875rem'
                            }
                          }}
                        >
                          <CloseIcon fontSize="inherit" />
                        </IconButton>
                      ) : (
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteMetric(metric.id, metric.name);
                          }}
                          sx={{
                            padding: '2px',
                            '& .MuiSvgIcon-root': {
                              fontSize: '0.875rem'
                            }
                          }}
                        >
                          <DeleteIcon fontSize="inherit" />
                        </IconButton>
                      )}
                    </Box>
                    <MetricCard 
                      type={isValidMetricType(metric.metric_type?.type_value) ? metric.metric_type.type_value : undefined}
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
      </Box>
    );
  };

  return (
    <>

      <PageContainer title="Metrics" breadcrumbs={[{ title: 'Metrics', path: '/metrics' }]}>
        <Box sx={{ 
          width: '100%',
          minHeight: '100%'
        }}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, bgcolor: 'background.paper' }}>
            <Tabs 
              value={value} 
              onChange={handleChange} 
              aria-label="metrics tabs"
            >
              <Tab 
                icon={<ChecklistIcon />} 
                iconPosition="start" 
                label="Selected Metrics" 
                {...a11yProps(0)} 
              />
              <Tab 
                icon={<ViewQuiltIcon />} 
                iconPosition="start" 
                label="Metrics Directory" 
                {...a11yProps(1)} 
              />
            </Tabs>
          </Box>

          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <CustomTabPanel value={value} index={0}>
              <Box sx={{ 
                width: '100%',
                pr: 2,
                pb: 4
              }}>
                {isLoading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                    <Typography>Loading behaviors and metrics...</Typography>
                  </Box>
                ) : error ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                    <Typography color="error">{error}</Typography>
                  </Box>
                ) : (
                  <>
                    {behaviors
                      .filter(b => b.name && b.name.trim() !== '')
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map(behavior => renderSection(behavior))}
                    
                    <Box 
                      sx={{ 
                        mt: 4, 
                        p: 3, 
                        border: '2px dashed',
                        borderColor: 'divider',
                        borderRadius: 1,
                        display: 'flex',
                        justifyContent: 'center',
                        mb: 8
                      }}
                    >
                      <Button
                        startIcon={<AddIcon />}
                        onClick={handleAddNewSection}
                        sx={{ color: 'text.secondary' }}
                      >
                        Add New Dimension
                      </Button>
                    </Box>
                  </>
                )}
              </Box>
            </CustomTabPanel>

            <CustomTabPanel value={value} index={1}>
              {renderMetricsDirectory()}
            </CustomTabPanel>
          </Box>
        </Box>
      </PageContainer>

      {/* Dialogs and Drawers */}
      {editingSection && (
        <SectionEditDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          title={editingSection.title}
          description={editingSection.description}
          onSave={handleSaveSection}
          onDelete={
            !isNewSection && 
            editingSection.key && 
            behaviorMetrics[editingSection.key] && 
            behaviorMetrics[editingSection.key].metrics.length === 0
              ? handleDeleteSection 
              : undefined
          }
          isNew={isNewSection}
          loading={drawerLoading}
          error={drawerError}
          organization_id={session?.user?.organization_id as UUID}
        />
      )}

      <Dialog
        open={deleteDialogOpen}
        onClose={handleCancelDelete}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          Remove Metric
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            Are you sure you want to remove the {metricToDelete?.title} metric from this dimension?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelDelete}>Cancel</Button>
          <Button onClick={handleConfirmDelete} color="error" autoFocus>
            Remove
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={deleteMetricDialogOpen}
        onClose={handleCancelDeleteMetric}
        aria-labelledby="delete-metric-dialog-title"
        aria-describedby="delete-metric-dialog-description"
      >
        <DialogTitle id="delete-metric-dialog-title">
          Delete Metric
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-metric-dialog-description">
            Are you sure you want to permanently delete the metric &quot;{metricToDeleteCompletely?.name}&quot;? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelDeleteMetric}>Cancel</Button>
          <Button onClick={handleConfirmDeleteMetric} color="error" autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

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
    </>
  );
} 