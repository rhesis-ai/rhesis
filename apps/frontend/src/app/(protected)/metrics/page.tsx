'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Grid from '@mui/material/Grid';
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
import SectionEditDrawer from './components/SectionEditDrawer';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
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
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import type { Behavior as ApiBehavior } from '@/utils/api-client/interfaces/behavior';
import type { Status } from '@/utils/api-client/interfaces/status';
import type { User } from '@/utils/api-client/interfaces/user';
import type { TypeLookup as MetricType } from '@/utils/api-client/interfaces/type-lookup';
import type { TypeLookup as BackendType } from '@/utils/api-client/interfaces/type-lookup';

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

const metricSections: MetricSections = {
  robustness: [
    {
      type: 'answer_relevancy',
      title: 'Answer Relevancy',
      description: 'Measures how relevant the answer is to the question',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: true,
      metricType: 'Grading'
    },
    {
      type: 'faithfulness',
      title: 'Faithfulness',
      description: 'Measures how faithful the answer is to the provided context',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: false,
      metricType: 'Grading'
    },
    {
      type: 'contextual_relevancy',
      title: 'Contextual Relevancy',
      description: 'Measures how relevant the context is to the question',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: false,
      metricType: 'Grading'
    }
  ],
  reliability: [
    {
      type: 'contextual_precision',
      title: 'Contextual Precision',
      description: 'Measures the precision of context usage in the answer',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: false,
      metricType: 'Grading'
    },
    {
      type: 'contextual_recall',
      title: 'Contextual Recall',
      description: 'Measures how much of the relevant context is used',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: false,
      metricType: 'Grading'
    },
    {
      type: 'answer_relevancy',
      title: 'Response Quality',
      description: 'Measures the overall quality and coherence of the response',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: true,
      metricType: 'Grading'
    }
  ],
  compliance: [
    {
      type: 'faithfulness',
      title: 'Policy Adherence',
      description: 'Measures compliance with defined policies and guidelines',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: true,
      metricType: 'Grading'
    },
    {
      type: 'contextual_precision',
      title: 'Data Privacy',
      description: 'Evaluates handling of sensitive information and privacy compliance',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: true,
      metricType: 'Grading'
    },
    {
      type: 'contextual_recall',
      title: 'Regulatory Coverage',
      description: 'Assesses coverage of relevant regulatory requirements',
      backend: 'deepeval',
      defaultThreshold: 0.5,
      requiresGroundTruth: true,
      metricType: 'Grading'
    }
  ]
};

interface Section {
  title: string;
  description: string;
  metrics: MetricSectionItem[];
}

interface FilterState {
  search: string;
  backend: string[];
  groundTruth: string[];
  type: string[];
}

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  groundTruth: [],
  type: []
};

interface FilterOptions {
  backend: { type_value: string }[];
  groundTruth: string[];
  type: { type_value: string; description: string }[];
}

const initialFilterOptions: FilterOptions = {
  backend: [],
  groundTruth: ['yes', 'no'],
  type: []
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

type MetricCardType = 'answer_relevancy' | 'faithfulness' | 'contextual_relevancy' | 'contextual_precision' | 'contextual_recall';

const mapMetricTypeToCardType = (apiType: string): MetricCardType => {
  const mapping: Record<string, MetricCardType> = {
    'answer-relevancy': 'answer_relevancy',
    'faithfulness': 'faithfulness',
    'contextual-relevancy': 'contextual_relevancy',
    'contextual-precision': 'contextual_precision',
    'contextual-recall': 'contextual_recall'
  };
  return mapping[apiType] || 'answer_relevancy'; // fallback to answer_relevancy if type not found
};

interface BehaviorMetrics {
  [behaviorId: string]: {
    metrics: MetricDetail[];
    isLoading: boolean;
    error: string | null;
  }
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
    key: string;
    title: string;
    description: string;
  } | null>(null);
  const [isNewSection, setIsNewSection] = React.useState(false);
  const [behaviors, setBehaviors] = React.useState<ApiBehavior[]>([]);
  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [sections, setSections] = React.useState<MetricSections>(metricSections);
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);
  const [filterOptions, setFilterOptions] = React.useState<FilterOptions>(initialFilterOptions);
  const [assignDialogOpen, setAssignDialogOpen] = React.useState(false);
  const [selectedMetric, setSelectedMetric] = React.useState<MetricDetail | null>(null);
  const [createMetricOpen, setCreateMetricOpen] = React.useState(false);
  const [behaviorMetrics, setBehaviorMetrics] = React.useState<BehaviorMetrics>({});

  // Fetch behaviors, metrics, and filter options
  React.useEffect(() => {
    const fetchData = async () => {
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

        setBehaviors(behaviorsData);
        setMetrics(metricsData.data || []);
        
        // Filter and set backend types and metric types
        const backendTypes = typeLookupData
          .filter((type: any) => type.type_name === 'BackendType')
          .map((type: any) => ({
            type_value: type.type_value.charAt(0).toUpperCase() + type.type_value.slice(1)
          }));

        const metricTypes = typeLookupData
          .filter((type: any) => type.type_name === 'MetricType')
          .map((type: any) => ({
            type_value: type.type_value.replace(/-/g, ' ').split(' ').map((word: string) => 
              word.charAt(0).toUpperCase() + word.slice(1)
            ).join(' '),
            description: type.description
          }));

        setFilterOptions(prev => ({
          ...prev,
          backend: backendTypes,
          type: metricTypes
        }));

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

    if (session?.session_token) {
      fetchData();
    }
  }, [session?.session_token, notifications]);

  // Function to fetch metrics for a behavior
  const fetchBehaviorMetrics = async (behaviorId: string) => {
    try {
      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: { metrics: [], isLoading: true, error: null }
      }));

      const response = await fetch(
        `https://rhesis-backend-dev-97484699177.us-central1.run.app/behaviors/${behaviorId}/metrics/?skip=0&limit=100&sort_by=created_at&sort_order=desc`,
        {
          headers: {
            'accept': 'application/json',
            'Authorization': `Bearer ${session?.session_token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch metrics for behavior');
      }

      const metricsData = await response.json();

      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: { metrics: metricsData, isLoading: false, error: null }
      }));
    } catch (err) {
      setBehaviorMetrics(prev => ({
        ...prev,
        [behaviorId]: { 
          metrics: [], 
          isLoading: false, 
          error: err instanceof Error ? err.message : 'Failed to load metrics' 
        }
      }));
    }
  };

  // Fetch metrics for each behavior when behaviors are loaded
  React.useEffect(() => {
    if (behaviors.length > 0 && session?.session_token) {
      behaviors.forEach(behavior => {
        if (behavior.name && behavior.name.trim() !== '') {
          fetchBehaviorMetrics(behavior.id);
        }
      });
    }
  }, [behaviors, session?.session_token]);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  const handleEditSection = (key: string, title: string, description: string) => {
    setEditingSection({ key, title, description });
    setIsNewSection(false);
    setDrawerOpen(true);
  };

  const handleAddNewSection = () => {
    setEditingSection({ key: '', title: '', description: '' });
    setIsNewSection(true);
    setDrawerOpen(true);
  };

  const handleSaveSection = (title: string, description: string) => {
    // TODO: Implement save functionality
    console.log('Saving section:', { title, description });
  };

  const handleDeleteSection = () => {
    if (editingSection) {
      // TODO: Implement delete functionality
      console.log('Deleting section:', editingSection.key);
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

      // Ground Truth filter
      const groundTruthMatch = filters.groundTruth.length === 0 ||
        (filters.groundTruth.includes('yes') && metric.ground_truth_required) ||
        (filters.groundTruth.includes('no') && !metric.ground_truth_required);

      // Type filter
      const typeMatch = filters.type.length === 0 ||
        (metric.metric_type?.type_value && filters.type.includes(metric.metric_type.type_value));

      return searchMatch && backendMatch && groundTruthMatch && typeMatch;
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
      const response = await fetch(
        `https://rhesis-backend-dev-97484699177.us-central1.run.app/metrics/${metricId}/behaviors/${behaviorId}`,
        {
          method: 'POST',
          headers: {
            'accept': 'application/json',
            'Authorization': `Bearer ${session?.session_token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to assign metric to behavior');
      }

      // Update local state to reflect the change
      setMetrics(prevMetrics => 
        prevMetrics.map(metric => 
          metric.id === metricId 
            ? { ...metric, behavior_id: behaviorId }
            : metric
        )
      );
      
      notifications.show('Successfully assigned metric to behavior', {
        severity: 'success',
        autoHideDuration: 4000
      });
    } catch (err) {
      notifications.show('Failed to assign metric to behavior', {
        severity: 'error',
        autoHideDuration: 4000
      });
    }
  };

  // Function to remove a metric from a behavior
  const handleRemoveMetricFromBehavior = async (behaviorId: string, metricId: string) => {
    try {
      const response = await fetch(
        `https://rhesis-backend-dev-97484699177.us-central1.run.app/metrics/${metricId}/behaviors/${behaviorId}`,
        {
          method: 'DELETE',
          headers: {
            'accept': 'application/json',
            'Authorization': `Bearer ${session?.session_token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to remove metric from behavior');
      }

      // Update local state to reflect the change
      setMetrics(prevMetrics => 
        prevMetrics.map(metric => 
          metric.id === metricId 
            ? { ...metric, behavior_id: undefined }
            : metric
        )
      );
      
      notifications.show('Successfully removed metric from behavior', {
        severity: 'success',
        autoHideDuration: 4000
      });
    } catch (err) {
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

  // Function to check if any filter is active
  const hasActiveFilters = () => {
    return filters.search !== '' || 
           filters.backend.length > 0 || 
           filters.groundTruth.length > 0 || 
           filters.type.length > 0;
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
    const behaviorData = behaviorMetrics[behavior.id] || { metrics: [], isLoading: true, error: null };
    const { metrics: behaviorMetricsList, isLoading: metricsLoading, error: metricsError } = behaviorData;

    return (
      <Box sx={{ mb: 4 }} key={behavior.id}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6">
            {behavior.name || 'Unnamed Behavior'}
          </Typography>
          <IconButton 
            onClick={() => handleEditSection(behavior.id, behavior.name, behavior.description || '')}
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
        <Grid container spacing={3}>
          {metricsLoading ? (
            <Grid item xs={12}>
              <Box sx={{ textAlign: 'center', py: 2 }}>
                <Typography>Loading metrics...</Typography>
              </Box>
            </Grid>
          ) : metricsError ? (
            <Grid item xs={12}>
              <Box sx={{ textAlign: 'center', py: 2 }}>
                <Typography color="error">{metricsError}</Typography>
              </Box>
            </Grid>
          ) : behaviorMetricsList.length > 0 ? (
            behaviorMetricsList.map((metric) => (
              <Grid item xs={12} md={4} key={metric.id}>
                <Box sx={{ position: 'relative' }}>
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
                    type={mapMetricTypeToCardType(metric.metric_type?.type_value || 'answer_relevancy')}
                    title={metric.name}
                    description={metric.description}
                    backend={metric.backend_type?.type_value || 'custom'}
                    defaultThreshold={metric.threshold ?? 0.5}
                    requiresGroundTruth={false}
                  />
                </Box>
              </Grid>
            ))
          ) : (
            <Grid item xs={12}>
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
                    setSelectedMetric(null);
                    setAssignDialogOpen(true);
                  }}
                >
                  Add Metric
                </Button>
              </Paper>
            </Grid>
          )}
        </Grid>
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

              {/* Ground Truth Filter */}
              <FormControl sx={{ minWidth: 200, flex: 1 }} size="small">
                <InputLabel id="ground-truth-filter-label">Ground Truth</InputLabel>
                <Select
                  labelId="ground-truth-filter-label"
                  id="ground-truth-filter"
                  multiple
                  value={filters.groundTruth}
                  onChange={(e) => handleFilterChange('groundTruth', e.target.value as string[])}
                  label="Ground Truth"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.length === 0 ? (
                        <em>Select ground truth</em>
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
                    <em>Select ground truth</em>
                  </MenuItem>
                  {filterOptions.groundTruth.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Type Filter */}
              <FormControl sx={{ minWidth: 200, flex: 1 }} size="small">
                <InputLabel id="type-filter-label">Type</InputLabel>
                <Select
                  labelId="type-filter-label"
                  id="type-filter"
                  multiple
                  value={filters.type}
                  onChange={(e) => handleFilterChange('type', e.target.value as string[])}
                  label="Type"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.length === 0 ? (
                        <em>Select type</em>
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
                    <em>Select type</em>
                  </MenuItem>
                  {filterOptions.type.map((option) => (
                    <MenuItem key={option.type_value} value={option.type_value}>
                      <Box>
                        <Typography>{option.type_value}</Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {option.description}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </Stack>
        </Box>

        {/* Metrics Grid */}
        <Box sx={{ p: 3, flex: 1, overflow: 'auto' }}>
          <Grid container spacing={3}>
            {filteredMetrics.map((metric) => {
              const assignedBehavior = activeBehaviors.find(b => metric.behaviors?.includes(b.id));
              
              return (
                <Grid item xs={12} md={4} key={metric.id}>
                  <Box sx={{ position: 'relative' }}>
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
                      {assignedBehavior && (
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveMetricFromBehavior(assignedBehavior.id, metric.id);
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
                      )}
                    </Box>
                    <MetricCard 
                      type={mapMetricTypeToCardType(metric.metric_type?.type_value || 'answer_relevancy')}
                      title={metric.name}
                      description={metric.description}
                      backend={metric.backend_type?.type_value || 'custom'}
                      defaultThreshold={metric.threshold ?? 0.5}
                      requiresGroundTruth={false}
                      usedIn={assignedBehavior ? assignedBehavior.name : undefined}
                    />
                  </Box>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      </Box>
    );
  };

  return (
    <PageContainer title="Metrics" breadcrumbs={[{ title: 'Metrics', path: '/metrics' }]}>
      <Box sx={{ 
        flexGrow: 1, 
        display: 'flex', 
        flexDirection: 'column',
        minHeight: 'calc(100vh - 180px)',
        pb: 4
      }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
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
                  .filter(b => b.name && b.name.trim() !== '') // Filter out empty behaviors
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

        {editingSection && (
          <SectionEditDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            title={editingSection.title}
            description={editingSection.description}
            onSave={handleSaveSection}
            onDelete={handleDeleteSection}
            isNew={isNewSection}
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
    </PageContainer>
  );
} 