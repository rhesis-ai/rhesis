'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  FormControl,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
  SelectChangeEvent,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import FolderIcon from '@mui/icons-material/Folder';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PsychologyIcon from '@mui/icons-material/Psychology';
import ChatIcon from '@mui/icons-material/Chat';
import WebIcon from '@mui/icons-material/Web';
import DevicesIcon from '@mui/icons-material/Devices';
import CodeIcon from '@mui/icons-material/Code';
import TerminalIcon from '@mui/icons-material/Terminal';
import StorageIcon from '@mui/icons-material/Storage';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

// Map of icon names to components
const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Psychology: PsychologyIcon,
  Chat: ChatIcon,
  Web: WebIcon,
  Devices: DevicesIcon,
  Code: CodeIcon,
  Terminal: TerminalIcon,
  Storage: StorageIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  Dashboard: DashboardIcon,
  ShoppingCart: ShoppingCartIcon,
  VideogameAsset: VideogameAssetIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

interface ProjectSelectorProps {
  selectedProjectId: string | null;
  onProjectChange: (projectId: string | null) => void;
}

/**
 * ProjectSelector Component
 * Allows users to select a project to associate with test generation
 */
export default function ProjectSelector({
  selectedProjectId,
  onProjectChange,
}: ProjectSelectorProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: session } = useSession();

  useEffect(() => {
    loadProjects();
  }, [session]);

  const loadProjects = async () => {
    if (!session?.session_token) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const apiFactory = new ApiClientFactory(session.session_token);
      const projectsClient = apiFactory.getProjectsClient();

      // Fetch all projects
      const projectsResponse = await projectsClient.getProjects({
        limit: 100,
        skip: 0,
        sort_by: 'name',
        sort_order: 'asc',
      });

      // Handle both array and paginated response formats
      let projectsArray: Project[] = [];
      if (Array.isArray(projectsResponse)) {
        projectsArray = projectsResponse;
      } else if (projectsResponse && Array.isArray(projectsResponse.data)) {
        projectsArray = projectsResponse.data;
      }

      // Filter out projects with empty names
      const validProjects = projectsArray.filter(
        p => p.id && p.name && p.name.trim() !== ''
      );

      setProjects(validProjects);
    } catch (err) {
      console.error('Error loading projects:', err);
      setError('Failed to load projects. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    onProjectChange(value || null);
  };

  const getProjectById = (projectId: string): Project | undefined => {
    return projects.find(project => project.id === projectId);
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading projects...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (projects.length === 0) {
    return (
      <Alert severity="info">
        No projects available. Please create a project first.
      </Alert>
    );
  }

  return (
    <Box>
      <FormControl fullWidth>
        <Select
          id="project-selector"
          value={selectedProjectId || ''}
          onChange={handleChange}
          displayEmpty
          renderValue={selected => {
            if (!selected) {
              return <em>None</em>;
            }
            const project = getProjectById(selected);
            const IconComponent =
              project?.icon && ICON_MAP[project.icon]
                ? ICON_MAP[project.icon]
                : FolderIcon;
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <IconComponent fontSize="small" color="action" />
                <Typography variant="body2">{project?.name}</Typography>
              </Box>
            );
          }}
        >
          <MenuItem value="">
            <em>None</em>
          </MenuItem>
          {projects.map(project => {
            const IconComponent =
              project.icon && ICON_MAP[project.icon]
                ? ICON_MAP[project.icon]
                : FolderIcon;
            return (
              <MenuItem key={project.id} value={project.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <IconComponent fontSize="small" color="action" />
                  <Box>
                    <Typography variant="body2">{project.name}</Typography>
                    {project.description && (
                      <Typography variant="caption" color="text.secondary">
                        {project.description.length > 80
                          ? `${project.description.substring(0, 80)}...`
                          : project.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
              </MenuItem>
            );
          })}
        </Select>
      </FormControl>
    </Box>
  );
}
