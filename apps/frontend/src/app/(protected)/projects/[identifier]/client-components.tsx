'use client';

import * as React from 'react';
import {
  Typography,
  Box,
  Paper,
  Grid,
  Chip,
  Divider,
  useTheme,
  Button,
  Avatar,
  IconButton,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import EditIcon from '@mui/icons-material/Edit';
import DevicesIcon from '@mui/icons-material/Devices';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DoNotDisturbAltIcon from '@mui/icons-material/DoNotDisturbAlt';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import EditDrawer from './edit-drawer';

// Import additional icons
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
  AccountTree: AccountTreeIcon,
};

// Function to get project icon based on project icon or use case
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

// Function to get environment color
const getEnvironmentColor = (environment?: string) => {
  if (!environment) return 'default';

  switch (environment.toLowerCase()) {
    case 'production':
      return 'success';
    case 'staging':
      return 'warning';
    case 'development':
      return 'info';
    default:
      return 'default';
  }
};

export function EditDrawerWrapper({
  project,
  sessionToken,
}: {
  project: Project;
  sessionToken: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [apiFactory] = React.useState(() => new ApiClientFactory(sessionToken));

  React.useEffect(() => {
    const handleOpenDrawer = () => setOpen(true);
    window.addEventListener('openEditDrawer', handleOpenDrawer);
    return () => window.removeEventListener('openEditDrawer', handleOpenDrawer);
  }, []);

  const handleSave = async (updatedProject: Partial<Project>) => {
    const projectsClient = apiFactory.getProjectsClient();
    await projectsClient.updateProject(project.id, updatedProject);
    // Refresh the page to show updated data
    window.location.reload();
  };

  return (
    <EditDrawer
      open={open}
      onClose={() => setOpen(false)}
      project={project}
      onSave={handleSave}
      sessionToken={sessionToken}
    />
  );
}

export function ProjectContent({ project }: { project: Project }) {
  const theme = useTheme();
  return (
    <Paper sx={{ p: 3, mb: 4 }}>
      <Grid container spacing={3}>
        {/* Project Header */}
        <Grid size={12}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Avatar sx={{ bgcolor: 'primary.main', mr: 2 }}>
              {getProjectIcon(project)}
            </Avatar>
            <Typography variant="h5">{project.name}</Typography>
            {project.is_active !== undefined && (
              <Chip
                icon={
                  project.is_active ? (
                    <CheckCircleIcon fontSize="small" />
                  ) : (
                    <DoNotDisturbAltIcon fontSize="small" />
                  )
                }
                label={project.is_active ? 'Active' : 'Inactive'}
                size="small"
                color={project.is_active ? 'success' : 'error'}
                variant="outlined"
                sx={{ ml: 2 }}
              />
            )}
          </Box>
          <Divider sx={{ mb: 3 }} />

          {/* Project Info */}
          <Grid container spacing={3}>
            <Grid
              size={{
                xs: 12,
                md: 6,
              }}
            >
              {/* Project Description */}
              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle1"
                  sx={{ fontWeight: 'bold', mb: 1 }}
                >
                  Description
                </Typography>
                <Typography variant="body1">
                  {project.description || 'No description provided'}
                </Typography>
              </Box>

              {/* Project Owner */}
              {project.owner && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 'bold', mb: 1 }}
                  >
                    Owner
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Avatar
                      src={project.owner.picture}
                      alt={project.owner.name || project.owner.email}
                      sx={{ width: 32, height: 32 }}
                    >
                      <PersonIcon />
                    </Avatar>
                    <Typography variant="body1">
                      {project.owner.name || project.owner.email}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Grid>

            <Grid
              size={{
                xs: 12,
                md: 6,
              }}
            >
              {/* Project Environment & Use Case */}
              {(project.environment || project.useCase) && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 'bold', mb: 1 }}
                  >
                    Environment & Type
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {project.environment && (
                      <Chip
                        label={project.environment}
                        size="medium"
                        variant="outlined"
                        color={getEnvironmentColor(project.environment)}
                      />
                    )}
                    {project.useCase && (
                      <Chip
                        label={project.useCase}
                        size="medium"
                        variant="outlined"
                        color="primary"
                      />
                    )}
                  </Box>
                </Box>
              )}

              {/* Created Date */}
              {project.createdAt && (
                <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 3 }}>
                  <CalendarTodayIcon
                    sx={{
                      fontSize: theme => theme.iconSizes.medium,
                      color: 'text.secondary',
                      mr: 2,
                      mt: 0.5,
                    }}
                  />
                  <Box>
                    <Typography
                      variant="subtitle1"
                      sx={{ fontWeight: 'bold', mb: 1 }}
                    >
                      Created At
                    </Typography>
                    <Typography variant="body1">
                      {new Date(project.createdAt).toLocaleDateString()}{' '}
                      {new Date(project.createdAt).toLocaleTimeString()}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Grid>
          </Grid>

          {/* Tags Section */}
          {project.tags && project.tags.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Divider sx={{ mb: 3 }} />
              <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                <LocalOfferIcon
                  sx={{
                    fontSize: theme => theme.iconSizes.medium,
                    color: 'text.secondary',
                    mr: 2,
                    mt: 0.5,
                  }}
                />
                <Box>
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 'bold', mb: 1 }}
                  >
                    Tags
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {project.tags.map((tag: string) => (
                      <Chip
                        key={tag}
                        label={tag}
                        size="medium"
                        variant="outlined"
                        color="secondary"
                      />
                    ))}
                  </Box>
                </Box>
              </Box>
            </Box>
          )}
        </Grid>
      </Grid>
    </Paper>
  );
}
