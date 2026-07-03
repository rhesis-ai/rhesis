'use client';

import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { endpointKeys, projectKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  Endpoint,
  EndpointTestRequest,
} from '@/utils/api-client/interfaces/endpoint';
import { EndpointCreate } from '@/utils/api-client/endpoints-client';
import {
  Project,
  ProjectsQueryParams,
} from '@/utils/api-client/interfaces/project';
import { PaginationParams } from '@/utils/api-client/interfaces/pagination';

const STALE_TIME = 5 * 60_000;

/** Flattened, project-joined row for a single-dropdown endpoint picker. */
export interface EndpointOption {
  endpointId: string;
  endpointName: string;
  projectId: string;
  projectName: string;
  environment: Endpoint['environment'];
}

export function useEndpoints(
  sessionToken: string,
  params: Partial<PaginationParams> = {},
  enabled = true
) {
  return useQuery<Endpoint[]>({
    queryKey: endpointKeys.list(
      params.$filter ?? '',
      params.skip ?? 0,
      params.limit ?? 100,
      params.sort_by ?? '',
      params.sort_order ?? ''
    ),
    queryFn: async () => {
      const response = await new ApiClientFactory(sessionToken)
        .getEndpointsClient()
        .getEndpoints(params);
      return response.data || [];
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useEndpoint(
  sessionToken: string,
  identifier: string,
  enabled = true
) {
  return useQuery<Endpoint>({
    queryKey: endpointKeys.detail(identifier),
    queryFn: () =>
      new ApiClientFactory(sessionToken)
        .getEndpointsClient()
        .getEndpoint(identifier),
    enabled: enabled && !!sessionToken && !!identifier,
    staleTime: STALE_TIME,
  });
}

export function useProject(sessionToken: string, id: string, enabled = true) {
  return useQuery<Project>({
    queryKey: projectKeys.detail(id),
    queryFn: () =>
      new ApiClientFactory(sessionToken).getProjectsClient().getProject(id),
    enabled: enabled && !!sessionToken && !!id,
    staleTime: STALE_TIME,
  });
}

export function useProjects(
  sessionToken: string,
  params: ProjectsQueryParams = {},
  enabled = true
) {
  return useQuery<Project[]>({
    queryKey: projectKeys.list(
      params.$filter ?? '',
      params.skip ?? 0,
      params.limit ?? 100,
      params.sort_by ?? '',
      params.sort_order ?? ''
    ),
    queryFn: async () => {
      const response = await new ApiClientFactory(sessionToken)
        .getProjectsClient()
        .getProjects(params);
      return response.data || [];
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

/**
 * Project-joined endpoint options for a flat dropdown picker.
 *
 * Replaces the same fetch-both-lists-and-join-them block that was
 * independently copy-pasted into PlaygroundClient, EndpointSelector, and
 * ExplorerDetail — each fetching its own uncached copy of both lists.
 */
export function useEndpointOptions(sessionToken: string, enabled = true) {
  const listParams = {
    sort_by: 'name',
    sort_order: 'asc' as const,
    limit: 100,
  };
  const {
    data: endpoints,
    isLoading: endpointsLoading,
    error: endpointsError,
  } = useEndpoints(sessionToken, listParams, enabled);
  const {
    data: projects,
    isLoading: projectsLoading,
    error: projectsError,
  } = useProjects(sessionToken, listParams, enabled);

  const options = useMemo<EndpointOption[]>(() => {
    if (!endpoints || !projects) return [];
    const projectMap = new Map(projects.map(p => [p.id.toString(), p.name]));
    return endpoints
      .filter((e): e is Endpoint & { project_id: string } => !!e.project_id)
      .map(e => ({
        endpointId: e.id,
        endpointName: e.name,
        projectId: e.project_id,
        projectName: projectMap.get(e.project_id) || 'Unknown Project',
        environment: e.environment,
      }))
      .sort((a, b) => {
        const projectCompare = a.projectName.localeCompare(b.projectName);
        if (projectCompare !== 0) return projectCompare;
        return a.endpointName.localeCompare(b.endpointName);
      });
  }, [endpoints, projects]);

  return {
    options,
    isLoading: endpointsLoading || projectsLoading,
    error: endpointsError || projectsError,
  };
}

export function useDeleteEndpoint(sessionToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      new ApiClientFactory(sessionToken)
        .getEndpointsClient()
        .deleteEndpoint(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: endpointKeys.all() });
    },
  });
}

export function useTestEndpoint(sessionToken: string) {
  return useMutation({
    mutationFn: (testConfig: EndpointTestRequest) =>
      new ApiClientFactory(sessionToken)
        .getEndpointsClient()
        .testEndpoint(testConfig),
  });
}

export function useInvokeEndpoint(sessionToken: string) {
  return useMutation({
    mutationFn: ({
      id,
      inputData,
    }: {
      id: string;
      inputData: Record<string, unknown>;
    }) =>
      new ApiClientFactory(sessionToken)
        .getEndpointsClient()
        .invokeEndpoint(id, inputData),
  });
}

export type { EndpointCreate };
