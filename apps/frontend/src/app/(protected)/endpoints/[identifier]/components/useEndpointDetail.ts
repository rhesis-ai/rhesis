'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '@mui/material/styles';
import { useSession } from 'next-auth/react';
import {
  Endpoint,
  EndpointEditData,
} from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { createEndpoint, invokeEndpoint } from '@/actions/endpoints';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { DEFAULT_TEST_INPUT } from './endpoint-detail-shared';
import { patchEndpointFields } from './endpointPatch';

export function useEndpointDetail(initialEndpoint: Endpoint) {
  const theme = useTheme();
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();

  const [endpoint, setEndpoint] = useState<Endpoint>(initialEndpoint);
  const [isDuplicating, setIsDuplicating] = useState(false);
  const [testResponse, setTestResponse] = useState('');
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
  const [testInput, setTestInput] = useState(DEFAULT_TEST_INPUT);
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState(true);

  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';
  const editorWrapperStyle = {
    width: '100%',
    boxSizing: 'border-box' as const,
    border: '1px solid',
    borderColor: 'divider',
    borderRadius: BORDER_RADIUS.sm,
    overflow: 'hidden' as const,
    '&:hover': { borderColor: 'text.primary' },
    '&:focus-within': {
      borderWidth: 2,
      borderColor: 'primary.main',
    },
  };

  useEffect(() => {
    setEndpoint(initialEndpoint);
  }, [initialEndpoint]);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        const sessionToken = session?.session_token || '';
        if (!sessionToken) return;

        const client = new ApiClientFactory(sessionToken).getProjectsClient();
        const response = await client.getProjects();
        const projectMap: Record<string, Project> = {};
        const projectsArray = Array.isArray(response)
          ? response
          : response?.data;

        if (Array.isArray(projectsArray)) {
          projectsArray.forEach((project: Project) => {
            if (project?.id) projectMap[project.id] = project;
          });
        }
        setProjects(projectMap);
      } catch (err) {
        console.error('[useEndpointDetail] Failed to load projects:', err);
      } finally {
        setLoadingProjects(false);
      }
    };

    if (session) fetchProjects();
  }, [session]);

  const saveFields = useCallback(
    async (payload: EndpointEditData) => {
      try {
        await patchEndpointFields(endpoint.id, payload);
        const { auth_token: _token, ...rest } = payload;
        setEndpoint(prev => ({ ...prev, ...rest }));
        notifications.show('Endpoint updated successfully', {
          severity: 'success',
        });
      } catch (error) {
        notifications.show(
          `Failed to update endpoint: ${(error as Error).message}`,
          { severity: 'error' }
        );
        throw error;
      }
    },
    [endpoint.id, notifications]
  );

  const duplicateEndpoint = useCallback(async () => {
    try {
      setIsDuplicating(true);
      const {
        id: _id,
        status: _status,
        status_id: _statusId,
        user_id: _userId,
        organization_id: _orgId,
        nano_id: _nanoId,
        created_at: _createdAt,
        updated_at: _updatedAt,
        ...rest
      } = endpoint as Endpoint & Record<string, unknown>;

      const copyMatch = endpoint.name.match(
        /^(.*?)\s*\(Copy(?:\s+(\d+))?\)\s*$/
      );
      let newName: string;
      if (copyMatch) {
        const base = copyMatch[1];
        const currentNum = copyMatch[2] ? parseInt(copyMatch[2], 10) : 1;
        newName = `${base} (Copy ${currentNum + 1})`;
      } else {
        newName = `${endpoint.name} (Copy)`;
      }

      const result = await createEndpoint({
        ...rest,
        name: newName,
      } as Omit<Endpoint, 'id'>);

      if (result.success && result.data) {
        notifications.show('Endpoint duplicated successfully', {
          severity: 'success',
        });
        router.push(`/endpoints/${result.data.id}`);
      } else {
        throw new Error(result.error || 'Failed to duplicate endpoint');
      }
    } catch (error) {
      notifications.show(
        `Failed to duplicate endpoint: ${(error as Error).message}`,
        { severity: 'error' }
      );
    } finally {
      setIsDuplicating(false);
    }
  }, [endpoint, notifications, router]);

  const runTest = useCallback(async () => {
    setIsTestingEndpoint(true);
    try {
      let inputData;
      try {
        inputData = JSON.parse(testInput);
      } catch {
        throw new Error('Invalid JSON input data');
      }

      const result = await invokeEndpoint(endpoint.id, inputData);
      if (result.success) {
        setTestResponse(JSON.stringify(result.data, null, 2));
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      setTestResponse(
        JSON.stringify(
          { success: false, error: (error as Error).message },
          null,
          2
        )
      );
    } finally {
      setIsTestingEndpoint(false);
    }
  }, [endpoint.id, testInput]);

  return {
    endpoint,
    projects,
    loadingProjects,
    isDuplicating,
    editorTheme,
    editorWrapperStyle,
    testInput,
    setTestInput,
    testResponse,
    isTestingEndpoint,
    saveFields,
    duplicateEndpoint,
    runTest,
  };
}

export type EndpointDetailContextValue = ReturnType<typeof useEndpointDetail>;
