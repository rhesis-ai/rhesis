import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Chip
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EntityType } from '@/utils/api-client/interfaces/tag';

// Import Material-UI icons
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DevicesIcon from '@mui/icons-material/Devices';
import WebIcon from '@mui/icons-material/Web';
import StorageIcon from '@mui/icons-material/Storage';
import CodeIcon from '@mui/icons-material/Code';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import TerminalIcon from '@mui/icons-material/Terminal';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import ChatIcon from '@mui/icons-material/Chat';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

// Map of icon names to components for easy lookup
const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon
};

// Get appropriate icon based on project type or use case
const getProjectIcon = (project: Project) => {
  // Check if a specific project icon was selected during creation
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }
  
  // Fall back to useCase-based icons if no specific icon is set
  if (project.useCase) {
    switch (project.useCase.toLowerCase()) {
      case 'chatbot':
        return <ChatIcon />;
      case 'assistant':
        return <PsychologyIcon />;
      case 'advisor':
        return <SmartToyIcon />;
      default:
        return <SmartToyIcon />;
    }
  }
  
  // Default icon
  return <SmartToyIcon />;
};

// Helper function to get environment color
const getEnvironmentColor = (environment: string) => {
  switch (environment.toLowerCase()) {
    case 'production':
      return 'success';
    case 'staging':
      return 'warning';
    default:
      return 'info';
  }
};

interface CreateTestRunProps {
  sessionToken: string;
  selectedTestSetIds: string[];
  onSuccess?: () => void;
  onError?: (error: string) => void;
  submitRef?: React.MutableRefObject<(() => Promise<void>) | undefined>;
}

export default function CreateTestRun({
  sessionToken,
  selectedTestSetIds,
  onSuccess,
  onError,
  submitRef
}: CreateTestRunProps) {
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>('');

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        
        // Fetch projects
        const projectsClient = clientFactory.getProjectsClient();
        const projectsData = await projectsClient.getProjects({
          sortOrder: 'asc'
        });
        setProjects(projectsData.data || []);
      } catch (error) {
        console.error('Error fetching initial data:', error);
        setProjects([]); // Ensure projects remains an empty array on error
        onError?.('Failed to load initial data');
      }
    };

    fetchInitialData();
  }, [sessionToken, onError]);

  useEffect(() => {
    const fetchEndpoints = async () => {
      if (!selectedProject) {
        setEndpoints([]);
        return;
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const endpointsClient = clientFactory.getEndpointsClient();
        const endpointsData = await endpointsClient.getEndpoints();
        // Filter endpoints by project_id
        const filteredEndpoints = endpointsData.data.filter(
          endpoint => endpoint.project_id === selectedProject
        );
        setEndpoints(filteredEndpoints || []);
      } catch (error) {
        console.error('Error fetching endpoints:', error);
        setEndpoints([]); // Ensure endpoints remains an empty array on error
        onError?.('Failed to load endpoints');
      }
    };

    fetchEndpoints();
  }, [selectedProject, sessionToken, onError]);

  const handleSubmit = async () => {
    if (!selectedEndpoint || selectedTestSetIds.length === 0) {
      onError?.('Please select an endpoint');
      return;
    }

    setLoading(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const endpointsClient = clientFactory.getEndpointsClient();
      
      // Execute test sets for the selected endpoint
      await endpointsClient.executeEndpoint(selectedEndpoint, selectedTestSetIds);
      
      onSuccess?.();
    } catch (error) {
      console.error('Error executing test sets:', error);
      onError?.('Failed to execute test sets');
    } finally {
      setLoading(false);
    }
  };

  // Attach submit handler to ref
  if (submitRef) {
    submitRef.current = handleSubmit;
  }

  return (
    <>
      <Typography variant="subtitle2" color="text.secondary">
        Test Run Details
      </Typography>

      <FormControl fullWidth>
        <InputLabel>Project</InputLabel>
        <Select
          value={selectedProject}
          onChange={(e) => {
            setSelectedProject(e.target.value);
            setSelectedEndpoint('');
          }}
          label="Project"
        >
          {(projects || []).map((project) => (
            <MenuItem key={project.id} value={project.id}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {getProjectIcon(project)}
                <Typography>{project.name}</Typography>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <FormControl fullWidth>
        <InputLabel>Endpoint</InputLabel>
        <Select
          value={selectedEndpoint}
          onChange={(e) => setSelectedEndpoint(e.target.value)}
          label="Endpoint"
          disabled={!selectedProject}
        >
          {(!endpoints || endpoints.length === 0) ? (
            <MenuItem disabled>
              <Typography color="text.secondary">
                {selectedProject ? 'No endpoints available for this project' : 'Select a project first'}
              </Typography>
            </MenuItem>
          ) : (
            endpoints.map((endpoint) => (
              <MenuItem key={endpoint.id} value={endpoint.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  <Typography>{endpoint.name}</Typography>
                  <Chip
                    label={endpoint.environment}
                    size="small"
                    color={getEnvironmentColor(endpoint.environment)}
                    sx={{ ml: 1, textTransform: 'capitalize' }}
                  />
                </Box>
              </MenuItem>
            ))
          )}
        </Select>
      </FormControl>
    </>
  );
} 