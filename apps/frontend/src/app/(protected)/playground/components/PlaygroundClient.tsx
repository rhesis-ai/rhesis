'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Chip,
  Stack,
} from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import { useSession } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { useWebSocket } from '@/hooks/useWebSocket';
import PlaygroundChat from './PlaygroundChat';

interface EndpointOption {
  endpointId: string;
  endpointName: string;
  projectId: string;
  projectName: string;
  environment: string;
}

/**
 * PlaygroundClient Component
 *
 * Main client component for the Playground feature.
 * Allows users to select an endpoint and chat with it interactively.
 */
export default function PlaygroundClient() {
  const { data: session } = useSession();
  const { isConnected } = useWebSocket();
  const searchParams = useSearchParams();

  const [endpointOptions, setEndpointOptions] = useState<EndpointOption[]>([]);
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(
    null
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initialEndpointApplied, setInitialEndpointApplied] = useState(false);

  // Apply initial endpoint from URL params after endpoints are loaded
  useEffect(() => {
    if (!initialEndpointApplied && endpointOptions.length > 0) {
      const endpointIdParam = searchParams.get('endpointId');
      if (endpointIdParam) {
        const matchingOption = endpointOptions.find(
          opt => opt.endpointId === endpointIdParam
        );
        if (matchingOption) {
          setSelectedEndpointId(endpointIdParam);
          setSelectedProjectId(matchingOption.projectId);
        }
      }
      setInitialEndpointApplied(true);
    }
  }, [endpointOptions, searchParams, initialEndpointApplied]);

  const loadEndpoints = useCallback(async () => {
    if (!session?.session_token) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const apiFactory = new ApiClientFactory(session.session_token);
      const projectsClient = apiFactory.getProjectsClient();
      const endpointsClient = apiFactory.getEndpointsClient();

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

      // Create a map of project IDs to project data
      const projectMap = new Map<string, Project>();
      projects.forEach((project: Project) => {
        projectMap.set(project.id.toString(), project);
      });

      // Build endpoint options with project information
      const options: EndpointOption[] = endpoints
        .filter(
          (endpoint: Endpoint): endpoint is Endpoint & { project_id: string } =>
            !!endpoint.project_id
        )
        .map(endpoint => {
          const project = projectMap.get(endpoint.project_id);
          return {
            endpointId: endpoint.id,
            endpointName: endpoint.name,
            projectId: endpoint.project_id,
            projectName: project?.name || 'Unknown Project',
            environment: endpoint.environment,
          };
        })
        .sort((a, b) => {
          const projectCompare = a.projectName.localeCompare(b.projectName);
          if (projectCompare !== 0) return projectCompare;
          return a.endpointName.localeCompare(b.endpointName);
        });

      setEndpointOptions(options);
    } catch (err) {
      setError('Failed to load endpoints. Please try again.');
      console.error('Failed to load endpoints:', err);
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  // Load endpoints on mount
  useEffect(() => {
    loadEndpoints();
  }, [loadEndpoints]);

  const handleEndpointChange = (event: any) => {
    const value = event.target.value;
    setSelectedEndpointId(value === '' ? null : value);

    // Find the project ID for the selected endpoint
    if (value) {
      const selectedOption = endpointOptions.find(
        opt => opt.endpointId === value
      );
      setSelectedProjectId(selectedOption?.projectId || null);
    } else {
      setSelectedProjectId(null);
    }
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

  return (
    <PageContainer title="Playground" breadcrumbs={[]}>
      {/* Description with connection status */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography color="text.secondary">
          Chat with your endpoints interactively to test their responses.
        </Typography>
        <Chip
          icon={isConnected ? <WifiIcon /> : <WifiOffIcon />}
          label={isConnected ? 'Connected' : 'Disconnected'}
          color={isConnected ? 'success' : 'default'}
          variant="outlined"
          size="small"
        />
      </Box>

      {/* Endpoint Selector */}
      <Paper
        elevation={1}
        sx={{
          p: 2,
          borderRadius: theme => theme.shape.borderRadius,
          mb: 2,
        }}
      >
        {isLoading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              Loading endpoints...
            </Typography>
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : endpointOptions.length === 0 ? (
          <Alert severity="info">
            No endpoints available. Please create an endpoint in a project
            first.
          </Alert>
        ) : (
          <FormControl fullWidth size="small">
            <InputLabel id="endpoint-selector-label">
              Select an Endpoint
            </InputLabel>
            <Select
              labelId="endpoint-selector-label"
              id="endpoint-selector"
              value={selectedEndpointId || ''}
              label="Select an Endpoint"
              onChange={handleEndpointChange}
            >
              <MenuItem value="">
                <Typography variant="body2" color="text.secondary">
                  Choose an endpoint to chat with...
                </Typography>
              </MenuItem>
              {endpointOptions.map(option => (
                <MenuItem key={option.endpointId} value={option.endpointId}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      width: '100%',
                    }}
                  >
                    <Typography variant="body2" sx={{ flexGrow: 1 }}>
                      {option.projectName} › {option.endpointName}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        ml: 2,
                        px: 1,
                        py: 0.25,
                        borderRadius: theme => theme.shape.borderRadius * 0.25,
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
          </FormControl>
        )}
      </Paper>

      {/* Chat Area */}
      <Box
        sx={{
          height: 'calc(100vh - 340px)',
          minHeight: 400,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {selectedEndpointId && selectedProjectId ? (
          <PlaygroundChat
            endpointId={selectedEndpointId}
            projectId={selectedProjectId}
          />
        ) : (
          <Paper
            elevation={1}
            sx={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: theme => theme.shape.borderRadius,
            }}
          >
            <Stack spacing={1} alignItems="center">
              <Typography variant="h6" color="text.secondary">
                Select an endpoint to start chatting
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Choose an endpoint from the dropdown above
              </Typography>
            </Stack>
          </Paper>
        )}
      </Box>
    </PageContainer>
  );
}
