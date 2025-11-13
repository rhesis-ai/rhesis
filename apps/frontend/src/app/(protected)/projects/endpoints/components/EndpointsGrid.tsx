'use client';

import React, { useState, useEffect } from 'react';
import { Chip, Paper, Box, Button, Typography, useTheme } from '@mui/material';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import {
  AddIcon,
  DeleteIcon,
  SmartToyIcon,
  DevicesIcon,
  WebIcon,
  StorageIcon,
  CodeIcon,
} from '@/components/icons';
import UploadIcon from '@mui/icons-material/UploadOutlined';
import {
  GridColDef,
  GridPaginationModel,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
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
  AccountTree: AccountTreeIcon,
};

// Get appropriate icon based on project type or use case
const getProjectIcon = (project: Project | undefined) => {
  if (!project) {
    return <SmartToyIcon />;
  }

  // Check if a specific project icon was selected during creation
  if (project.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }

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
  projectId?: string;
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
  onEndpointDeleted,
  projectId,
}: EndpointGridProps) {
  const theme = useTheme();
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
          const projectsArray = Array.isArray(response)
            ? response
            : response?.data;

          if (Array.isArray(projectsArray)) {
            projectsArray.forEach((project: Project) => {
              if (project && project.id) {
                projectMap[project.id] = project;
              }
            });
          }

          setProjects(projectMap);
        }
      } catch {
        // Error handled silently
      } finally {
        setLoadingProjects(false);
      }
    };

    if (session) {
      fetchProjects();
    }
  }, [session]);

  // Handle row selection
  const handleRowSelectionModelChange = (
    newSelection: GridRowSelectionModel
  ) => {
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
    } catch {
      // Error handled silently
    } finally {
      setDeleting(false);
    }
  };

  // Custom toolbar with right-aligned buttons
  const customToolbar = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        width: '100%',
        gap: 2,
      }}
    >
      {/* Delete button - shown when rows are selected */}
      {selectedRows.length > 0 && (
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={() => setDeleteDialogOpen(true)}
          disabled={deleting}
        >
          Delete {selectedRows.length} endpoint
          {selectedRows.length > 1 ? 's' : ''}
        </Button>
      )}

      {/* Spacer to push buttons to the right when no selection */}
      <Box sx={{ flexGrow: 1 }} />

      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          component={Link}
          href={
            projectId
              ? `/projects/${projectId}/endpoints/new`
              : '/projects/endpoints/new'
          }
          variant="outlined"
          startIcon={<AddIcon />}
        >
          New Endpoint
        </Button>
        <Button
          component={Link}
          href={
            projectId
              ? `/projects/${projectId}/endpoints/swagger`
              : '/projects/endpoints/swagger'
          }
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
      renderCell: params => {
        const endpoint = params.row as Endpoint;
        const project = endpoint.project_id
          ? projects[endpoint.project_id]
          : undefined;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                color: 'primary.main',
                '& svg': {
                  fontSize: theme.typography.h5.fontSize,
                },
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
      renderCell: params => (
        <Chip label={params.value} size="small" variant="outlined" />
      ),
    },
    {
      field: 'environment',
      headerName: 'Environment',
      flex: 0.8,
      renderCell: params => (
        <Chip label={params.value} size="small" variant="outlined" />
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
          linkPath={
            projectId
              ? `/projects/${projectId}/endpoints`
              : '/projects/endpoints'
          }
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
        message={`Are you sure you want to delete ${selectedRows.length} endpoint${selectedRows.length > 1 ? 's' : ''}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
        itemType="endpoints"
      />
    </>
  );
}
