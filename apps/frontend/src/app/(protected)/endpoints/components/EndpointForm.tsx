'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useImperativeHandle,
  useMemo,
  forwardRef,
} from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Box, Alert } from '@mui/material';
import StepNav from '@/components/common/StepNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useTestEndpoint } from '@/hooks/useEndpoints';
import { useCreateEndpoint } from '@/hooks/useCreateEndpoint';
import {
  AutoConfigureResult,
  Endpoint,
} from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { readActiveProjectId } from '@/utils/active-project';
import { getApiErrorMessage } from '@/utils/error-utils';
import AutoConfigureDrawer from './AutoConfigureDrawer';
import { DEFAULT_REQUEST_HEADERS } from './headerRows';
import TabOverview from './TabOverview';
import TabConnection from './TabConnection';
import TabMapping from './TabMapping';
import TabTest from './TabTest';
import type { EndpointTestResult } from './TestResponseCard';
import {
  bodyToRequestMapping,
  parseBodyMapping,
  parseResMapping,
  validateMappingJson,
} from './mappingUtils';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import type { TestOutput } from '@/utils/api-client/interfaces/test-results';
import {
  ENDPOINT_AUTH_TYPES,
  type EndpointAuthType,
} from '@/constants/endpoint-auth';
import {
  EMPTY_CLIENT_CREDENTIALS,
  authPayload,
  testAuthFields,
  validateClientCredentials,
  type ClientCredentialsDraft,
} from './endpointAuth';

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
  auth_type: EndpointAuthType;
  auth_token: string;
  client_credentials: ClientCredentialsDraft;
  request_headers: string;
  disable_tracing: boolean;
  timeout_seconds: string;
}

// Both start empty: the Mapping step asks for every field explicitly.
const DEFAULT_REQ_BODY = '{}';
const DEFAULT_RES_BODY = '{}';

const CREATE_STEPS = [
  { key: 'basics', label: 'Basics' },
  { key: 'connection', label: 'Connection' },
  { key: 'mapping', label: 'Mapping' },
  { key: 'test', label: 'Test' },
];
const LAST_STEP = CREATE_STEPS.length - 1;

const INPUT_VAR_RE = /\{\{\s*input\b/;

function hasOutputMapping(resBody: string): boolean {
  try {
    const parsed: unknown = JSON.parse(resBody);
    return (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof (parsed as Record<string, unknown>).output === 'string'
    );
  } catch {
    return false;
  }
}

function validateUrl(url: string) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export interface EndpointFormSubmitState {
  isSubmitting: boolean;
  /** The active step is complete, so Next (or Create on the last step) can run. */
  canAdvance: boolean;
  isLastStep: boolean;
  isFirstStep: boolean;
}

export interface EndpointFormProps {
  projectId?: string;
  onCreated?: () => void;
  /** Hide project picker — project is inferred from active project scope */
  hideProjectSelect?: boolean;
  onSubmitStateChange?: (state: EndpointFormSubmitState) => void;
}

export interface EndpointFormHandle {
  /** Moves to the next step, or creates the endpoint on the last one. */
  advance: () => void;
  back: () => void;
}

const EndpointForm = forwardRef<EndpointFormHandle, EndpointFormProps>(
  function EndpointForm(
    {
      projectId: projectIdProp,
      onCreated,
      hideProjectSelect = false,
      onSubmitStateChange,
    },
    ref
  ) {
    const router = useRouter();
    const params = useParams<{ identifier?: string }>();
    const projectIdFromUrl = projectIdProp ?? params?.identifier ?? '';

    const [activeTab, setActiveTab] = useState(0);
    const [reqBody, setReqBody] = useState<string>(DEFAULT_REQ_BODY);
    const [resBody, setResBody] = useState<string>(DEFAULT_RES_BODY);
    const [testResult, setTestResult] = useState<EndpointTestResult | null>(
      null
    );
    const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
    const [tabTestResult, setTabTestResult] =
      useState<EndpointTestResult | null>(null);
    const [isTabTestRunning, setIsTabTestRunning] = useState(false);
    // The setup each passing test ran against; a pass only counts while it still matches.
    const [mappingTestKey, setMappingTestKey] = useState<string | null>(null);
    const [tabTestKey, setTabTestKey] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [loadingProjects, setLoadingProjects] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [autoConfigureOpen, setAutoConfigureOpen] = useState(false);

    const { data: session, status } = useSession();
    const notifications = useNotifications();
    const { markStepComplete } = useOnboarding();
    const testEndpointMutation = useTestEndpoint();
    const createEndpoint = useCreateEndpoint();

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
      auth_type: ENDPOINT_AUTH_TYPES.BEARER_TOKEN,
      auth_token: '',
      client_credentials: EMPTY_CLIENT_CREDENTIALS,
      request_headers: DEFAULT_REQUEST_HEADERS,
      disable_tracing: false,
      timeout_seconds: '',
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
      if (hideProjectSelect) {
        setLoadingProjects(false);
        return;
      }

      const fetchProjects = async () => {
        if (!isAuthenticated(status)) {
          setLoadingProjects(false);
          return;
        }
        try {
          setLoadingProjects(true);
          const client = new ApiClientFactory().getProjectsClient();
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
    }, [session, hideProjectSelect, status]);

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
          if (r.rhesis) asJson[r.rhesis] = `$.${r.api}`;
        });
        setResBody(JSON.stringify(asJson, null, 2));
      }
      setFormData(prev => ({
        ...prev,
        request_headers: result.request_headers
          ? JSON.stringify(result.request_headers, null, 2)
          : prev.request_headers,
        url: result.url || prev.url,
        method: result.method || prev.method,
      }));
      setAutoConfigureOpen(false);
      notifications.show('Auto-configure mappings applied!', {
        severity: 'success',
      });
    };

    const isClientCredentials =
      formData.auth_type === ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS;
    const authError = isClientCredentials
      ? validateClientCredentials(formData.client_credentials, false)
      : null;
    // Only a bearer token is a value the test and auto-configure calls can use as is.
    const bearerToken = isClientCredentials ? '' : formData.auth_token;

    const connectionKey = useMemo(
      () =>
        JSON.stringify([
          formData.url,
          formData.method,
          formData.request_headers,
          formData.auth_type,
          formData.auth_token,
          formData.client_credentials,
          formData.endpoint_path,
          formData.response_format,
          reqBody,
        ]),
      [formData, reqBody]
    );
    // The test step also checks the response mapping, so a mapping edit needs a new run.
    const fullKey = `${connectionKey}${resBody}`;

    // A Test step result only describes the setup it ran against; drop it once
    // that changes, so the step shows green only after a new successful send.
    useEffect(() => {
      setTabTestResult(null);
    }, [fullKey]);

    const stepsValid = [
      Boolean(formData.name) && Boolean(formData.project_id),
      Boolean(formData.url) && validateUrl(formData.url) && authError === null,
      INPUT_VAR_RE.test(reqBody) &&
        hasOutputMapping(resBody) &&
        // Not keyed on resBody: the response is mapped from this test's result, after it ran.
        mappingTestKey === connectionKey,
      tabTestKey === fullKey,
    ];
    const firstInvalidStep = stepsValid.findIndex(valid => !valid);
    // Steps can be opened up to the first incomplete one; later ones wait for it.
    const maxReachableStep =
      firstInvalidStep === -1 ? LAST_STEP : firstInvalidStep;
    const canAdvance = stepsValid[activeTab];
    const isLastStep = activeTab === LAST_STEP;
    const isFirstStep = activeTab === 0;

    useEffect(() => {
      onSubmitStateChange?.({
        isSubmitting,
        canAdvance,
        isLastStep,
        isFirstStep,
      });
    }, [
      isSubmitting,
      canAdvance,
      isLastStep,
      isFirstStep,
      onSubmitStateChange,
    ]);

    const runTest = async (
      inputData: Record<string, unknown>,
      setResult: React.Dispatch<
        React.SetStateAction<EndpointTestResult | null>
      >,
      setTesting: React.Dispatch<React.SetStateAction<boolean>>,
      onPassed?: () => void
    ) => {
      setTesting(true);
      setResult(null);
      try {
        if (!formData.url || !validateUrl(formData.url)) {
          throw new Error('Enter a valid URL in the Connection step');
        }
        if (authError) {
          throw new Error(authError);
        }
        if (!isAuthenticated(status)) {
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

        const result = await testEndpointMutation.mutateAsync({
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
          ...testAuthFields(
            formData.auth_type,
            formData.auth_token,
            formData.client_credentials
          ),
          input_data: inputData,
          endpoint_path: formData.endpoint_path || undefined,
          response_format: (formData.response_format || 'json') as
            | 'json'
            | 'xml'
            | 'text',
        });

        const r = result as Record<string, unknown>;
        // A failed call to the target comes back as a 200 with the failure in the body.
        const failure = getEndpointFailure(r as unknown as TestOutput);
        const success = !failure && r.success !== false && !r.error;
        setResult({
          success,
          status: failure?.statusCode,
          response: r,
          error: failure ? failure.message || failure.summary : undefined,
        });
        if (success) onPassed?.();
      } catch (err) {
        setResult({ success: false, error: (err as Error).message ?? '' });
      } finally {
        setTesting(false);
      }
    };

    const handleRunTest = (inputData: Record<string, unknown>) => {
      const key = connectionKey;
      return runTest(inputData, setTestResult, setIsTestingEndpoint, () =>
        setMappingTestKey(key)
      );
    };

    const handleTabRunTest = (inputData: Record<string, unknown>) => {
      const key = fullKey;
      return runTest(inputData, setTabTestResult, setIsTabTestRunning, () =>
        setTabTestKey(key)
      );
    };

    const handleSubmit = useCallback(async () => {
      setError(null);

      if (!formData.url || !validateUrl(formData.url)) {
        setError('Please enter a valid URL');
        return;
      }

      if (authError) {
        setError(authError);
        return;
      }

      const reqError = validateMappingJson(reqBody);
      if (reqError) {
        setError(`Invalid JSON in request mapping: ${reqError}`);
        return;
      }

      const resError = validateMappingJson(resBody);
      if (resError) {
        setError(`Invalid JSON in response mapping: ${resError}`);
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
          response_mapping: JSON.parse(
            resBody
          ) as unknown as Endpoint['response_mapping'],
        };

        if (requestHeaders) {
          endpointData.request_headers =
            requestHeaders as unknown as Endpoint['request_headers'];
        }
        Object.assign(
          endpointData,
          authPayload(formData.auth_type, formData.client_credentials)
        );
        if (!isClientCredentials && formData.auth_token) {
          (endpointData as Record<string, unknown>).auth_token =
            formData.auth_token;
        }
        const parsedTimeout = parseInt(formData.timeout_seconds, 10);
        if (!isNaN(parsedTimeout) && parsedTimeout > 0) {
          endpointData.timeout_seconds = parsedTimeout;
        }

        const result = await createEndpoint(
          endpointData as Omit<Endpoint, 'id'>
        );
        if (!result.success) {
          // createEndpoint never throws on a business failure (a 402 from
          // an exhausted endpoints quota included) -- it returns
          // {success: false, error} instead, per its own doc comment.
          // Both callers used to ignore that and show "created
          // successfully" regardless.
          throw new Error(result.error);
        }
        markStepComplete('endpointSetup');
        notifications.show('Endpoint created successfully!', {
          severity: 'success',
        });
        if (onCreated) {
          onCreated();
        } else {
          router.push(
            projectIdFromUrl ? `/projects/${projectIdFromUrl}` : '/endpoints'
          );
        }
      } catch (err) {
        setError(getApiErrorMessage(err, 'Failed to create endpoint.'));
      } finally {
        setIsSubmitting(false);
      }
    }, [
      formData,
      authError,
      isClientCredentials,
      reqBody,
      resBody,
      createEndpoint,
      markStepComplete,
      notifications,
      onCreated,
      projectIdFromUrl,
      router,
    ]);

    useImperativeHandle(
      ref,
      () => ({
        advance: () => {
          if (!canAdvance) return;
          if (isLastStep) {
            void handleSubmit();
          } else {
            setError(null);
            setActiveTab(activeTab + 1);
          }
        },
        back: () => {
          setError(null);
          setActiveTab(Math.max(0, activeTab - 1));
        },
      }),
      [activeTab, canAdvance, isLastStep, handleSubmit]
    );

    // Enter in a one-line field moves on once the step is complete. Multi-line
    // fields keep Enter for new lines, and the last step never creates on Enter.
    const handleKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
      const target = e.target as HTMLElement;
      if (
        e.key !== 'Enter' ||
        e.shiftKey ||
        e.nativeEvent.isComposing ||
        target.tagName !== 'INPUT' ||
        // React bubbles through portals; ignore the auto-configure drawer's fields.
        !e.currentTarget.contains(target) ||
        isLastStep ||
        !canAdvance
      ) {
        return;
      }
      e.preventDefault();
      setError(null);
      setActiveTab(activeTab + 1);
    };

    return (
      <Box
        onKeyDown={handleKeyDown}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        <Box>
          <StepNav
            steps={CREATE_STEPS}
            activeIndex={activeTab}
            maxReachableIndex={maxReachableStep}
            onChange={setActiveTab}
            aria-label="Endpoint creation steps"
          />
        </Box>

        <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <DetailTabPanel value={activeTab} index={0} prefix="endpoint">
            <TabOverview
              formData={formData}
              onChange={handleChange}
              projects={projects}
              loadingProjects={loadingProjects}
              hideProjectSelect={hideProjectSelect}
            />
          </DetailTabPanel>

          <DetailTabPanel value={activeTab} index={1} prefix="endpoint">
            <TabConnection
              formData={formData}
              onChange={handleChange}
              onAutoConfigureOpen={() => setAutoConfigureOpen(true)}
            />
          </DetailTabPanel>

          <DetailTabPanel value={activeTab} index={2} prefix="endpoint">
            <TabMapping
              reqBody={reqBody}
              resBody={resBody}
              onReqBodyChange={setReqBody}
              onResBodyChange={setResBody}
              testResult={testResult}
              isTestingEndpoint={isTestingEndpoint}
              onRunTest={handleRunTest}
              resultIsCurrent={mappingTestKey === connectionKey}
            />
          </DetailTabPanel>

          {/* Kept mounted so typed test values and uploads survive leaving the step. */}
          <DetailTabPanel
            value={activeTab}
            index={3}
            prefix="endpoint"
            keepMounted
          >
            <TabTest
              url={formData.url}
              method={formData.method}
              reqBody={reqBody}
              resBody={resBody}
              requestHeaders={formData.request_headers}
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
        </Box>

        <AutoConfigureDrawer
          open={autoConfigureOpen}
          onClose={() => setAutoConfigureOpen(false)}
          onApply={handleAutoConfigureApply}
          url={formData.url || ''}
          authToken={bearerToken}
          method={formData.method || 'POST'}
        />
      </Box>
    );
  }
);

export default EndpointForm;
