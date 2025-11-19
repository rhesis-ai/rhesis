'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';

interface EndpointOption {
  endpointId: string;
  endpointName: string;
  projectId: string;
  projectName: string;
  environment: string;
}

interface EndpointSelectorProps {
  selectedEndpointId: string | null;
  onEndpointChange: (endpointId: string | null) => void;
}

/**
 * EndpointSelector Component
 * Allows users to select an endpoint from available projects
 * Displays format: "Project Name > Endpoint Name (Environment)"
 */
export default function EndpointSelector({
  selectedEndpointId,
  onEndpointChange,
}: EndpointSelectorProps) {
  const [endpointOptions, setEndpointOptions] = useState<EndpointOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: session } = useSession();

  useEffect(() => {
    loadEndpoints();
  }, [session]);

  const loadEndpoints = async () => {
    if (!session?.session_token) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Create API clients
      const apiFactory = new ApiClientFactory(session.session_token);
      const projectsClient = apiFactory.getProjectsClient();
      const endpointsClient = apiFactory.getEndpointsClient();

      // Fetch all projects and endpoints
      const [projectsResponse, endpointsResponse] = await Promise.all([
        projectsClient.getProjects({ limit: 100 }),
        endpointsClient.getEndpoints({ limit: 100 }),
      ]);

      // Handle both array and paginated response formats
      const projects = Array.isArray(projectsResponse)
        ? projectsResponse
        : projectsResponse?.data || [];

      const endpoints = Array.isArray(endpointsResponse)
        ? endpointsResponse
        : endpointsResponse?.data || [];

      // Create a map of project IDs to project names
      const projectMap = new Map<string, string>();
      projects.forEach((project: Project) => {
        projectMap.set(project.id.toString(), project.name);
      });

      // Build endpoint options with project information
      const options: EndpointOption[] = endpoints
        .filter((endpoint: Endpoint) => endpoint.project_id) // Only include endpoints with projects
        .map((endpoint: Endpoint) => ({
          endpointId: endpoint.id,
          endpointName: endpoint.name,
          projectId: endpoint.project_id!,
          projectName:
            projectMap.get(endpoint.project_id!) || 'Unknown Project',
          environment: endpoint.environment,
        }))
        .sort((a, b) => {
          // Sort by project name, then endpoint name
          const projectCompare = a.projectName.localeCompare(b.projectName);
          if (projectCompare !== 0) return projectCompare;
          return a.endpointName.localeCompare(b.endpointName);
        });

      setEndpointOptions(options);
    } catch (err) {
      setError('Failed to load endpoints. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (event: any) => {
    const value = event.target.value;
    onEndpointChange(value === '' ? null : value);
  };

  const formatEnvironment = (env: string) => {
    return env.charAt(0).toUpperCase() + env.slice(1);
  };

  const getEnvironmentColor = (env: string) => {
    switch (env.toLowerCase()) {
      case 'production':
        return 'error.main';
      case 'staging':
        return 'warning.main';
      case 'development':
        return 'info.main';
      default:
        return 'text.secondary';
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading endpoints...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (endpointOptions.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No endpoints available. Please create an endpoint in a project first.
      </Alert>
    );
  }

  return (
    <FormControl fullWidth sx={{ mb: 3 }}>
      <InputLabel id="endpoint-selector-label">
        Select Endpoint for Test Preview
      </InputLabel>
      <Select
        labelId="endpoint-selector-label"
        id="endpoint-selector"
        value={selectedEndpointId || ''}
        label="Select Endpoint for Test Preview"
        onChange={handleChange}
      >
        <MenuItem value="">
          <Typography variant="body2" color="text.secondary">
            None (Skip preview)
          </Typography>
        </MenuItem>
        {endpointOptions.map(option => (
          <MenuItem key={option.endpointId} value={option.endpointId}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography variant="body2" sx={{ flexGrow: 1 }}>
                {option.projectName} › {option.endpointName}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  ml: 2,
                  px: 1,
                  py: 0.25,
                  borderRadius: theme => theme.shape.borderRadius / 4,
                  bgcolor: 'action.hover',
                  color: getEnvironmentColor(option.environment),
                  fontWeight: 'medium',
                }}
              >
                {formatEnvironment(option.environment)}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Select>
      {selectedEndpointId && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          Test samples will show live responses from this endpoint in the next
          step.
        </Typography>
      )}
    </FormControl>
  );
}
