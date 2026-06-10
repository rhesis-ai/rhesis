'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Box, Tab, Tabs, Alert } from '@mui/material';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import ActionBar from '@/components/common/ActionBar';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  AutoConfigureResult,
  Endpoint,
} from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { createEndpoint } from '@/actions/endpoints';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { readActiveProjectId } from '@/utils/active-project';
import AutoConfigureModal from './AutoConfigureModal';
import TabBasics from './tabs/TabBasics';
import TabHeaders from './tabs/TabHeaders';
import TabBody from './tabs/TabBody';
import TabTest from './tabs/TabTest';
import {
  bodyToRequestMapping,
  parseBodyMapping,
  parseResMapping,
} from './mappingUtils';

export interface FormData {
  name: string;
  description: string;
  connection_type: 'REST';
  url: string;
  environment: string;
  config_source: string;
  response_format: string;
  method: string;
  endpoint_path: string;
  project_id: string;
  organization_id: string;
  auth_token: string;
  request_headers: string;
  disable_tracing: boolean;
}

const DEFAULT_REQ_BODY =
  '{\n  "messages": [{"role": "user", "content": "{{ input }}"}]\n}';

const DEFAULT_RES_BODY = '{\n  "output": "$.choices[0].message.content"\n}';

function validateUrl(url: string) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export default function EndpointForm() {
  const router = useRouter();
  const params = useParams<{ identifier?: string }>();
  const projectIdFromUrl = params?.identifier || '';

  const [activeTab, setActiveTab] = useState(0);
  const [reqBody, setReqBody] = useState<string>(DEFAULT_REQ_BODY);
  const [resBody, setResBody] = useState<string>(DEFAULT_RES_BODY);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    status?: number;
    response?: Record<string, unknown>;
    error?: string;
  } | null>(null);
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
  const [tabTestResult, setTabTestResult] = useState<{
    success: boolean;
    status?: number;
    response?: Record<string, unknown>;
    error?: string;
  } | null>(null);
  const [isTabTestRunning, setIsTabTestRunning] = useState(false);
  const [testPassed, setTestPassed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [autoConfigureOpen, setAutoConfigureOpen] = useState(false);

  const { data: session } = useSession();
  const notifications = useNotifications();
  const { markStepComplete } = useOnboarding();

  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    connection_type: 'REST',
    url: '',
    environment: 'development',
    config_source: 'manual',
    response_format: 'json',
    method: 'POST',
    endpoint_path: '',
    project_id: '',
    organization_id: '',
    auth_token: '',
    request_headers: '{}',
    disable_tracing: false,
  });

  // Set project_id from URL parameter, then fall back to active project cookie
  useEffect(() => {
    const resolved = projectIdFromUrl || readActiveProjectId() || '';
    if (resolved) {
      setFormData(prev => ({
        ...prev,
        project_id: resolved,
      }));
    }
  }, [projectIdFromUrl]);

  useEffect(() => {
    const fetchProjects = async () => {
      if (!session?.session_token) {
        setLoadingProjects(false);
        return;
      }
      try {
        setLoadingProjects(true);
        const client = new ApiClientFactory(
          session.session_token
        ).getProjectsClient();
        const data = await client.getProjects();
        setProjects(Array.isArray(data) ? data : data?.data || []);
      } catch {
        setError('Failed to load projects. Please try again later.');
        setProjects([]);
      } finally {
        setLoadingProjects(false);
      }
    };
    fetchProjects();
  }, [session]);

  const handleChange = (field: keyof FormData, value: unknown) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleAutoConfigureApply = (result: AutoConfigureResult) => {
    if (result.request_mapping) {
      setReqBody(
        parseBodyMapping(result.request_mapping as Record<string, unknown>)
      );
    }
    if (result.response_mapping) {
      const rows = parseResMapping(
        result.response_mapping as Record<string, string>
      );
      const asJson: Record<string, string> = {};
      rows.forEach(r => {
        if (r.rhesis) asJson[r.rhesis] = r.api;
      });
      setResBody(JSON.stringify(asJson, null, 2));
    }
    if (result.request_headers) {
      setFormData(prev => ({
        ...prev,
        request_headers: JSON.stringify(result.request_headers, null, 2),
        url: result.url || prev.url,
        method: result.method || prev.method,
      }));
    }
    setAutoConfigureOpen(false);
    notifications.show('Auto-configure mappings applied!', {
      severity: 'success',
    });
  };

  const step1Valid =
    Boolean(formData.url) &&
    validateUrl(formData.url) &&
    Boolean(formData.name) &&
    Boolean(formData.project_id);

  const runTest = async (
    inputData: Record<string, unknown>,
    setResult: React.Dispatch<
      React.SetStateAction<{
        success: boolean;
        status?: number;
        response?: Record<string, unknown>;
        error?: string;
      } | null>
    >,
    setTesting: React.Dispatch<React.SetStateAction<boolean>>,
    onSuccess?: () => void
  ) => {
    setTesting(true);
    setResult(null);
    try {
      if (!formData.url || !validateUrl(formData.url)) {
        throw new Error('Please enter a valid URL in step 1');
      }
      if (!session?.session_token) {
        throw new Error('Session token not available');
      }

      let requestHeaders: Record<string, string> = {};
      try {
        if (formData.request_headers?.trim()) {
          requestHeaders = JSON.parse(formData.request_headers);
        }
      } catch {
        throw new Error('Invalid JSON in request headers');
      }

      const client = new ApiClientFactory(
        session.session_token
      ).getEndpointsClient();
      const result = await client.testEndpoint({
        connection_type: 'REST',
        url: formData.url,
        method: formData.method,
        request_headers: requestHeaders,
        request_mapping: bodyToRequestMapping(reqBody),
        response_mapping: (() => {
          try {
            return JSON.parse(resBody);
          } catch {
            return {};
          }
        })(),
        auth_type: 'bearer_token',
        auth_token: formData.auth_token || '',
        input_data: inputData,
        endpoint_path: formData.endpoint_path || undefined,
        response_format: (formData.response_format || 'json') as
          | 'json'
          | 'xml'
          | 'text',
      });

      const r = result as Record<string, unknown>;
      const success = r.success !== false && !r.error;
      setResult({ success: Boolean(success), response: r });
      if (success) onSuccess?.();
    } catch (err) {
      const msg = (err as Error).message ?? '';
      const display = msg.includes('500')
        ? 'The server encountered an error processing the response. Check the backend logs for details.'
        : msg;
      setResult({ success: false, error: display });
    } finally {
      setTesting(false);
    }
  };

  const handleRunTest = (inputData: Record<string, unknown>) =>
    runTest(inputData, setTestResult, setIsTestingEndpoint, () =>
      setTestPassed(true)
    );

  const handleTabRunTest = (inputData: Record<string, unknown>) =>
    runTest(inputData, setTabTestResult, setIsTabTestRunning);

  const handleSubmit = async () => {
    setError(null);

    if (!formData.url || !validateUrl(formData.url)) {
      setError('Please enter a valid URL');
      return;
    }

    setIsSubmitting(true);
    try {
      let requestHeaders: Record<string, string> | undefined;
      try {
        if (
          formData.request_headers?.trim() &&
          formData.request_headers !== '{}'
        ) {
          requestHeaders = JSON.parse(formData.request_headers);
        }
      } catch {
        // ignore invalid headers
      }

      const endpointData: Partial<Omit<Endpoint, 'id'>> = {
        name: formData.name,
        description: formData.description,
        connection_type: formData.connection_type,
        url: formData.url,
        environment: formData.environment as Endpoint['environment'],
        config_source: formData.config_source as Endpoint['config_source'],
        response_format:
          formData.response_format as Endpoint['response_format'],
        method: formData.method,
        endpoint_path: formData.endpoint_path,
        project_id: formData.project_id,
        disable_tracing: formData.disable_tracing,
        request_mapping: bodyToRequestMapping(
          reqBody
        ) as unknown as Endpoint['request_mapping'],
        response_mapping: (() => {
          try {
            return JSON.parse(resBody);
          } catch {
            return {};
          }
        })() as unknown as Endpoint['response_mapping'],
      };

      if (requestHeaders) {
        endpointData.request_headers =
          requestHeaders as unknown as Endpoint['request_headers'];
      }
      if (formData.auth_token) {
        (endpointData as Record<string, unknown>).auth_token =
          formData.auth_token;
      }

      await createEndpoint(endpointData as Omit<Endpoint, 'id'>);
      markStepComplete('endpointSetup');
      notifications.show('Endpoint created successfully!', {
        severity: 'success',
      });
      router.push(
        projectIdFromUrl ? `/projects/${projectIdFromUrl}` : '/endpoints'
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () =>
    router.push(
      projectIdFromUrl ? `/projects/${projectIdFromUrl}` : '/endpoints'
    );

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(_e, v) => setActiveTab(v)}
          aria-label="endpoint creation tabs"
        >
          <Tab
            label="Basics"
            id="endpoint-tab-0"
            aria-controls="endpoint-tabpanel-0"
          />
          <Tab
            label="Headers"
            id="endpoint-tab-1"
            aria-controls="endpoint-tabpanel-1"
          />
          <Tab
            label="Mapping"
            id="endpoint-tab-2"
            aria-controls="endpoint-tabpanel-2"
          />
          <Tab
            label="Test"
            id="endpoint-tab-3"
            aria-controls="endpoint-tabpanel-3"
          />
        </Tabs>
      </Box>

      <DetailTabPanel value={activeTab} index={0} prefix="endpoint">
        <TabBasics
          formData={formData}
          onChange={handleChange}
          projects={projects}
          loadingProjects={loadingProjects}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="endpoint">
        <TabHeaders
          formData={formData}
          onChange={handleChange}
          showAuthToken={showAuthToken}
          onToggleAuthToken={() => setShowAuthToken(v => !v)}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="endpoint">
        <TabBody
          reqBody={reqBody}
          resBody={resBody}
          onReqBodyChange={setReqBody}
          onResBodyChange={setResBody}
          testResult={testResult}
          isTestingEndpoint={isTestingEndpoint}
          onRunTest={handleRunTest}
          onAutoConfigureOpen={() => setAutoConfigureOpen(true)}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="endpoint">
        <TabTest
          url={formData.url}
          method={formData.method}
          reqBody={reqBody}
          resBody={resBody}
          requestHeaders={formData.request_headers}
          authToken={formData.auth_token}
          testResult={tabTestResult}
          isTestingEndpoint={isTabTestRunning}
          onRunTest={handleTabRunTest}
        />
      </DetailTabPanel>

      {error && (
        <Box sx={{ mt: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      <ActionBar
        leftButton={{
          label: 'Cancel',
          onClick: handleCancel,
          variant: 'outlined',
        }}
        rightButton={{
          label: 'Save endpoint',
          onClick: handleSubmit,
          variant: 'contained',
          disabled: isSubmitting || !step1Valid,
        }}
      />

      <AutoConfigureModal
        open={autoConfigureOpen}
        onClose={() => setAutoConfigureOpen(false)}
        onApply={handleAutoConfigureApply}
        url={formData.url || ''}
        authToken={formData.auth_token || ''}
        method={formData.method || 'POST'}
      />
    </Box>
  );
}
