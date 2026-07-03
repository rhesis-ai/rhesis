'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Stack,
  IconButton,
  Tooltip,
} from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import PlaygroundIcon from '@/components/PlaygroundIcon';
import EndpointsIcon from '@/components/EndpointsIcon';
import { useSession } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { playgroundPanelSx } from './playgroundPanelSx';
import PlaygroundChat from './PlaygroundChat';
import PlaygroundEndpointDrawer from './PlaygroundEndpointDrawer';
import { EndpointOption, formatEndpointLabel } from './playgroundEndpointUtils';

/**
 * Placeholder shown when no endpoint is selected.
 */
function ChatPlaceholder({
  label,
  onClose,
  onSplit,
}: {
  label?: string;
  onClose?: () => void;
  onSplit?: () => void;
}) {
  return (
    <Paper
      elevation={0}
      sx={{
        ...playgroundPanelSx,
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {(label || onSplit) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: label ? 'space-between' : 'flex-end',
            px: 1.5,
            minHeight: theme => theme.spacing(4),
            bgcolor: theme => theme.palette.greyscale.surface1,
            borderBottom: 1,
            borderColor: theme => theme.palette.greyscale.border,
          }}
        >
          {label && (
            <Typography
              variant="captionBold"
              sx={{ color: theme => theme.palette.greyscale.label }}
            >
              {label}
            </Typography>
          )}
          {onClose && (
            <IconButton
              size="small"
              onClick={onClose}
              sx={{ color: theme => theme.palette.greyscale.label, p: 0.25 }}
            >
              <CloseIcon fontSize="inherit" />
            </IconButton>
          )}
          {onSplit && (
            <Tooltip title="Add chat pane">
              <IconButton
                size="small"
                onClick={onSplit}
                sx={{ color: theme => theme.palette.greyscale.label, p: 0.25 }}
              >
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      )}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Stack spacing={1} alignItems="center">
          <PlaygroundIcon
            sx={{
              fontSize: theme => theme.typography.h3.fontSize,
              color: 'primary.main',
            }}
          />
          <Typography
            variant="h6"
            sx={{ color: 'primary.main', fontWeight: 600 }}
          >
            Select an endpoint to start chatting
          </Typography>
        </Stack>
      </Box>
    </Paper>
  );
}

/**
 * PlaygroundClient Component
 *
 * Main client component for the Playground feature.
 * Allows users to select an endpoint and chat with it interactively.
 */
export default function PlaygroundClient() {
  const { data: session } = useSession();
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
  const [isSplit, setIsSplit] = useState(false);
  const [endpointDrawerOpen, setEndpointDrawerOpen] = useState(false);

  const selectedOption = useMemo(
    () =>
      endpointOptions.find(opt => opt.endpointId === selectedEndpointId) ??
      null,
    [endpointOptions, selectedEndpointId]
  );

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

  const handleReset = useCallback(() => {
    setSelectedEndpointId(null);
    setSelectedProjectId(null);
    setIsSplit(false);
  }, []);

  const handleEndpointSelect = useCallback(
    (endpointId: string) => {
      setSelectedEndpointId(endpointId);
      const selected = endpointOptions.find(
        opt => opt.endpointId === endpointId
      );
      setSelectedProjectId(selected?.projectId ?? null);
    },
    [endpointOptions]
  );

  const openEndpointDrawer = useCallback(() => {
    setEndpointDrawerOpen(true);
  }, []);

  const hasActiveSession = !!(selectedEndpointId || isSplit);

  const endpointFabTooltip = selectedOption
    ? formatEndpointLabel(selectedOption)
    : 'Select endpoint';

  return (
    <PageLayout
      title="Playground"
      description="Chat with your endpoints interactively to test their responses and generate test cases from your conversations."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<EndpointsIcon />}
            tooltip={endpointFabTooltip}
            aria-label="Select endpoint"
            onClick={openEndpointDrawer}
            loading={isLoading && endpointDrawerOpen}
          />
          <Fab
            icon={<RestartAltIcon />}
            tooltip="Reset playground"
            aria-label="Reset playground"
            onClick={handleReset}
            disabled={!hasActiveSession}
          />
        </FabGroup>
      }
    >
      {/* Chat Area */}
      <Box
        sx={{
          height: 'calc(100vh - 260px)',
          minHeight: 400,
          display: 'flex',
          flexDirection: 'row',
          gap: 1,
        }}
      >
        {/* Pane 1 */}
        {selectedEndpointId && selectedProjectId && selectedOption ? (
          <PlaygroundChat
            key="pane-left"
            endpointId={selectedEndpointId}
            projectId={selectedProjectId}
            endpointName={selectedOption.endpointName}
            projectName={selectedOption.projectName}
            environment={selectedOption.environment}
            label={isSplit ? 'Chat 1' : undefined}
            onClose={isSplit ? () => setIsSplit(false) : undefined}
            onSplit={!isSplit ? () => setIsSplit(true) : undefined}
            onChangeEndpoint={openEndpointDrawer}
          />
        ) : (
          <ChatPlaceholder
            label={isSplit ? 'Chat 1' : undefined}
            onClose={isSplit ? () => setIsSplit(false) : undefined}
            onSplit={!isSplit ? () => setIsSplit(true) : undefined}
          />
        )}

        {/* Pane 2 (split mode only) */}
        {isSplit &&
          (selectedEndpointId && selectedProjectId && selectedOption ? (
            <PlaygroundChat
              key="pane-right"
              endpointId={selectedEndpointId}
              projectId={selectedProjectId}
              endpointName={selectedOption.endpointName}
              projectName={selectedOption.projectName}
              environment={selectedOption.environment}
              label="Chat 2"
              onClose={() => setIsSplit(false)}
              onChangeEndpoint={openEndpointDrawer}
            />
          ) : (
            <ChatPlaceholder label="Chat 2" onClose={() => setIsSplit(false)} />
          ))}
      </Box>

      <PlaygroundEndpointDrawer
        open={endpointDrawerOpen}
        onClose={() => setEndpointDrawerOpen(false)}
        endpointOptions={endpointOptions}
        selectedEndpointId={selectedEndpointId}
        isLoading={isLoading}
        error={error}
        onSelect={handleEndpointSelect}
      />
    </PageLayout>
  );
}
