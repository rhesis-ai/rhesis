'use client';

import { useCallback, useMemo } from 'react';
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
  ProjectCreate,
  ProjectsQueryParams,
} from '@/utils/api-client/interfaces/project';
import { PaginationParams } from '@/utils/api-client/interfaces/pagination';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';

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
  params: Partial<PaginationParams> = {},
  enabled = true,
  initialData?: Endpoint[]
) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Endpoint[]>({
    queryKey: endpointKeys.list(
      params.$filter ?? '',
      params.skip ?? 0,
      params.limit ?? 100,
      params.sort_by ?? '',
      params.sort_order ?? ''
    ),
    queryFn: async () => {
      const response = await new ApiClientFactory()
        .getEndpointsClient()
        .getEndpoints(params);
      return response.data || [];
    },
    enabled: enabled && isAuthenticated,
    initialData,
    staleTime: STALE_TIME,
  });
}

export function useEndpoint(
  identifier: string,
  enabled = true,
  initialData?: Endpoint
) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Endpoint>({
    queryKey: endpointKeys.detail(identifier),
    queryFn: () =>
      new ApiClientFactory().getEndpointsClient().getEndpoint(identifier),
    enabled: enabled && isAuthenticated && !!identifier,
    initialData,
    staleTime: STALE_TIME,
  });
}

export function useProject(id: string, enabled = true, initialData?: Project) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Project>({
    queryKey: projectKeys.detail(id),
    queryFn: () => new ApiClientFactory().getProjectsClient().getProject(id),
    enabled: enabled && isAuthenticated && !!id,
    initialData,
    staleTime: STALE_TIME,
  });
}

export function useProjects(
  params: ProjectsQueryParams = {},
  enabled = true,
  initialData?: Project[]
) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Project[]>({
    queryKey: projectKeys.list(
      params.$filter ?? '',
      params.skip ?? 0,
      params.limit ?? 100,
      params.sort_by ?? '',
      params.sort_order ?? ''
    ),
    queryFn: async () => {
      const response = await new ApiClientFactory()
        .getProjectsClient()
        .getProjects(params);
      return response.data || [];
    },
    enabled: enabled && isAuthenticated,
    initialData,
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
export function useEndpointOptions(
  enabled = true,
  initialEndpoints?: Endpoint[],
  initialProjects?: Project[]
) {
  const listParams = {
    sort_by: 'name',
    sort_order: 'asc' as const,
    limit: 100,
  };
  const {
    data: endpoints,
    isLoading: endpointsLoading,
    error: endpointsError,
  } = useEndpoints(listParams, enabled, initialEndpoints);
  const {
    data: projects,
    isLoading: projectsLoading,
    error: projectsError,
  } = useProjects(listParams, enabled, initialProjects);

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

export function useDeleteEndpoint() {
  const queryClient = useQueryClient();
  const isAuthenticated = useIsAuthenticated();
  const invalidateUsage = useInvalidateUsage();
  return useMutation({
    mutationFn: (id: string) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      return new ApiClientFactory().getEndpointsClient().deleteEndpoint(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: endpointKeys.all() });
      // Endpoints are a stock resource: deleting one frees quota, and the
      // endpoints gate reads the cached count.
      invalidateUsage();
    },
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  const isAuthenticated = useIsAuthenticated();
  const invalidateUsage = useInvalidateUsage();
  return useCallback(
    async (data: ProjectCreate) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      const project = await new ApiClientFactory()
        .getProjectsClient()
        .createProject(data);
      queryClient.invalidateQueries({ queryKey: projectKeys.all() });
      // Projects are a stock resource: creating one consumes quota, and the
      // projects gate reads the cached count.
      invalidateUsage();
      return project;
    },
    [queryClient, isAuthenticated, invalidateUsage]
  );
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  const isAuthenticated = useIsAuthenticated();
  const invalidateUsage = useInvalidateUsage();
  return useCallback(
    async (id: string) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      await new ApiClientFactory().getProjectsClient().deleteProject(id);
      queryClient.invalidateQueries({ queryKey: projectKeys.all() });
      // Deleting a project frees quota, and the projects gate reads the
      // cached count.
      invalidateUsage();
    },
    [queryClient, isAuthenticated, invalidateUsage]
  );
}

export function useTestEndpoint() {
  const isAuthenticated = useIsAuthenticated();
  return useMutation({
    mutationFn: (testConfig: EndpointTestRequest) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      return new ApiClientFactory()
        .getEndpointsClient()
        .testEndpoint(testConfig);
    },
  });
}

export function useInvokeEndpoint() {
  const isAuthenticated = useIsAuthenticated();
  return useMutation({
    mutationFn: ({
      id,
      inputData,
    }: {
      id: string;
      inputData: Record<string, unknown>;
    }) => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }
      return new ApiClientFactory()
        .getEndpointsClient()
        .invokeEndpoint(id, inputData);
    },
  });
}

export type { EndpointCreate };
