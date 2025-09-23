'use client';

import React, { useState, useEffect } from 'react';
import { Chip, Paper, Box, Button, Typography, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, useTheme } from '@mui/material';
import { useRouter } from 'next/navigation';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { AddIcon } from '@/components/icons';
import UploadIcon from '@mui/icons-material/UploadOutlined';
import { DeleteIcon } from '@/components/icons';
import { GridColDef, GridPaginationModel, GridRowSelectionModel } from '@mui/x-data-grid';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';

// Import icons for dynamic project icon rendering
import { SmartToyIcon, DevicesIcon, WebIcon, StorageIcon, CodeIcon } from '@/components/icons';
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
  onEndpointDeleted?: () => void;
}


export default function EndpointGrid({ 
  endpoints,
  loading = false,
  totalCount = 0,
  onPaginationModelChange,
  paginationModel = {
    page: 0,
    pageSize: 10,
  },
  onEndpointDeleted
}: EndpointGridProps) {
  const theme = useTheme();
  const router = useRouter();
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
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

  // Handle row selection
  const handleRowSelectionModelChange = (newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  };

  // Handle delete endpoints
  const handleDeleteEndpoints = async () => {
    if (!session?.session_token || selectedRows.length === 0) return;

    try {
      setDeleting(true);
      const apiFactory = new ApiClientFactory(session.session_token);
      const endpointsClient = apiFactory.getEndpointsClient();

      // Delete all selected endpoints
      await Promise.all(
        selectedRows.map(id => endpointsClient.deleteEndpoint(id as string))
      );

      // Clear selection and close dialog
      setSelectedRows([]);
      setDeleteDialogOpen(false);

      // Refresh the data
      if (onEndpointDeleted) {
        onEndpointDeleted();
      }
    } catch (error) {
      console.error('Error deleting endpoints:', error);
      // You might want to show a toast notification here
    } finally {
      setDeleting(false);
    }
  };

  // Custom toolbar with right-aligned buttons
  const customToolbar = (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', gap: 2 }}>
      {/* Delete button - shown when rows are selected */}
      {selectedRows.length > 0 && (
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={() => setDeleteDialogOpen(true)}
          disabled={deleting}
        >
          Delete {selectedRows.length} endpoint{selectedRows.length > 1 ? 's' : ''}
        </Button>
      )}
      
      {/* Spacer to push buttons to the right when no selection */}
      <Box sx={{ flexGrow: 1 }} />
      
      <Box sx={{ display: 'flex', gap: 2 }}>
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
                  fontSize: theme.typography.h5.fontSize
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
        />
      ),
    },
  ];

  return (
    <>
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
          checkboxSelection
          disableRowSelectionOnClick
          rowSelectionModel={selectedRows}
          onRowSelectionModelChange={handleRowSelectionModelChange}
          disablePaperWrapper={true}
        />
      </Paper>

      {/* Delete confirmation dialog */}
      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteEndpoints}
        isLoading={deleting}
        title={`Delete Endpoint${selectedRows.length > 1 ? 's' : ''}`}
        message={`Are you sure you want to delete ${selectedRows.length} endpoint${selectedRows.length > 1 ? 's' : ''}? This action cannot be undone.`}
        itemType="endpoints"
      />
    </>
  );
} 