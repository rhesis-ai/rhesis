'use client';

import React, { useState, useEffect } from 'react';
import { Chip, Paper, Box, Button, Typography } from '@mui/material';
import { useRouter } from 'next/navigation';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import AddIcon from '@mui/icons-material/Add';
import UploadIcon from '@mui/icons-material/Upload';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// Import icons for dynamic project icon rendering
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
const getProjectIcon = (project: Project | undefined) => {
  if (!project) {
    console.log('No project provided to getProjectIcon');
    return <SmartToyIcon />;
  }
  
  console.log('Project in getProjectIcon:', project);
  console.log('Project icon:', project.icon);
  
  // Check if a specific project icon was selected during creation
  if (project.icon && ICON_MAP[project.icon]) {
    console.log('Found matching icon in ICON_MAP:', project.icon);
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }
  
  console.log('No matching icon found, using default');
  // Fall back to a default icon
  return <SmartToyIcon />;
};

interface EndpointGridProps {
  endpoints: Endpoint[];
  loading?: boolean;
  totalCount?: number;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  paginationModel?: GridPaginationModel;
}

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

export default function EndpointGrid({ 
  endpoints,
  loading = false,
  totalCount = 0,
  onPaginationModelChange,
  paginationModel = {
    page: 0,
    pageSize: 10,
  }
}: EndpointGridProps) {
  const router = useRouter();
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const { data: session } = useSession();

  // Fetch projects when component mounts
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        const sessionToken = session?.session_token || '';
        
        if (sessionToken) {
          const client = new ApiClientFactory(sessionToken).getProjectsClient();
          const response = await client.getProjects();
          
          // Create a map for faster lookups
          const projectMap: Record<string, Project> = {};
          
          // Handle both paginated response and direct array
          const projectsArray = Array.isArray(response) ? response : response?.data;
          
          console.log('Fetched projects response:', response);
          console.log('Projects array:', projectsArray);
          
          if (Array.isArray(projectsArray)) {
            projectsArray.forEach((project: Project) => {
              if (project && project.id) {
                console.log('Adding project to map:', project);
                projectMap[project.id] = project;
              }
            });
          } else {
            console.warn('Projects response is not an array:', response);
          }
          
          console.log('Final project map:', projectMap);
          setProjects(projectMap);
        }
      } catch (err) {
        console.error('Error fetching projects:', err);
      } finally {
        setLoadingProjects(false);
      }
    };

    if (session) {
      fetchProjects();
    }
  }, [session]);

  // Custom toolbar with right-aligned buttons
  const customToolbar = (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', width: '100%', gap: 2 }}>
      <Button 
        component={Link} 
        href="/endpoints/new" 
        variant="outlined" 
        startIcon={<AddIcon />}
      >
        New Endpoint
      </Button>
      <Button 
        component={Link} 
        href="/endpoints/swagger" 
        variant="contained" 
        startIcon={<UploadIcon />}
      >
        Import Swagger
      </Button>
    </Box>
  );

  const columns: GridColDef[] = [
    {
      field: 'project',
      headerName: 'Project',
      flex: 1.2,
      renderCell: (params) => {
        const endpoint = params.row as Endpoint;
        const project = endpoint.project_id ? projects[endpoint.project_id] : undefined;
        
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box 
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                color: 'primary.main',
                '& svg': {
                  fontSize: '1.5rem'
                }
              }}
            >
              {getProjectIcon(project)}
            </Box>
            <Typography variant="body2">
              {project ? project.name : 'No project'}
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
    },
    {
      field: 'protocol',
      headerName: 'Protocol',
      flex: 0.7,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          variant="outlined"
          color="primary"
        />
      ),
    },
    {
      field: 'environment',
      headerName: 'Environment',
      flex: 0.8,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          variant="outlined"
          color={getEnvironmentColor(params.value as string)}
        />
      ),
    },
  ];

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <BaseDataGrid
        rows={endpoints}
        columns={columns}
        loading={loading || loadingProjects}
        density="comfortable"
        customToolbarContent={customToolbar}
        linkPath="/endpoints"
        linkField="id"
        serverSidePagination={true}
        totalRows={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={onPaginationModelChange}
        pageSizeOptions={[10, 25, 50]}
      />
    </Paper>
  );
} 