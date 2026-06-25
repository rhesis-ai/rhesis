'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Collapse,
  IconButton,
  Link,
  Typography,
} from '@mui/material';
import {
  AutoFixHighIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import EditableSection from '@/components/common/EditableSection';
import { SectionCard } from '@/components/common/SectionCard';
import { useNotifications } from '@/components/common/NotificationContext';
import { AutoConfigureResult } from '@/utils/api-client/interfaces/endpoint';
import { testEndpointMapping } from '@/actions/endpoints';
import MappingEditor from '../../components/MappingEditor';
import AutoConfigureDrawer from '../../components/AutoConfigureDrawer';
import {
  bodyToRequestMapping,
  parseBodyMapping,
  parseResMapping,
} from '../../components/mappingUtils';
import { useEndpointDetailContext } from './EndpointDetailContext';

interface MappingDraft {
  reqBody: string;
  resBody: string;
}

function mappingFromEndpoint(endpoint: {
  request_mapping?: Record<string, unknown>;
  response_mapping?: Record<string, unknown>;
}): MappingDraft {
  return {
    reqBody: parseBodyMapping(endpoint.request_mapping ?? {}),
    resBody: JSON.stringify(endpoint.response_mapping ?? {}, null, 2),
  };
}

export default function EndpointMappingTab() {
  const { endpoint, saveFields } = useEndpointDetailContext();
  const notifications = useNotifications();
  const [autoConfigureOpen, setAutoConfigureOpen] = useState(false);
  const [manualExpanded, setManualExpanded] = useState(true);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    status?: number;
    response?: Record<string, unknown>;
    error?: string;
  } | null>(null);
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);

  const mappingInitial = useMemo(
    () => mappingFromEndpoint(endpoint),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [endpoint.request_mapping, endpoint.response_mapping] // intentional: only re-derive when mappings change, not on every endpoint field update
  );

  if (endpoint.connection_type === 'SDK') {
    return null;
  }

  const handleAutoConfigureApply = async (result: AutoConfigureResult) => {
    const next: MappingDraft = { ...mappingFromEndpoint(endpoint) };
    if (result.request_mapping) {
      next.reqBody = parseBodyMapping(
        result.request_mapping as Record<string, unknown>
      );
    }
    if (result.response_mapping) {
      const asJson: Record<string, string> = {};
      parseResMapping(
        result.response_mapping as Record<string, string>
      ).forEach(row => {
        if (row.rhesis) asJson[row.rhesis] = `$.${row.api}`;
      });
      next.resBody = JSON.stringify(asJson, null, 2);
    }

    const payload: {
      request_mapping: Record<string, unknown>;
      response_mapping: Record<string, string>;
      request_headers?: Record<string, string>;
      url?: string;
      method?: string;
    } = {
      request_mapping: bodyToRequestMapping(next.reqBody),
      response_mapping: JSON.parse(next.resBody) as Record<string, string>,
    };

    if (result.request_headers) {
      payload.request_headers = result.request_headers;
    }
    if (result.url) payload.url = result.url;
    if (result.method) payload.method = result.method;

    await saveFields(payload);
    setAutoConfigureOpen(false);
    notifications.show('Auto-configure mappings applied!', {
      severity: 'success',
    });
  };

  const handleRunTest = async (
    inputData: Record<string, unknown>,
    reqBody: string,
    resBody: string
  ) => {
    setIsTestingEndpoint(true);
    setTestResult(null);
    try {
      let responseMapping: Record<string, string> = {};
      try {
        responseMapping = JSON.parse(resBody);
      } catch {
        throw new Error('Invalid response mapping JSON');
      }
      const result = await testEndpointMapping(
        endpoint.id,
        inputData,
        bodyToRequestMapping(reqBody) as Record<string, unknown>,
        responseMapping
      );
      if (!result.success) {
        throw new Error(result.error ?? 'Test failed');
      }
      const r = result.data as Record<string, unknown>;
      const success = r.success !== false && !r.error;
      setTestResult({ success: Boolean(success), response: r });
    } catch (err) {
      const msg = (err as Error).message ?? '';
      const display = msg.includes('500')
        ? 'The server encountered an error processing the response. Check the backend logs for details.'
        : msg;
      setTestResult({ success: false, error: display });
    } finally {
      setIsTestingEndpoint(false);
    }
  };

  const testResponse = (() => {
    if (!testResult) return '';
    if (testResult.response)
      return JSON.stringify(testResult.response, null, 2);
    if (testResult.error)
      return JSON.stringify({ error: testResult.error }, null, 2);
    return '';
  })();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <SectionCard
        title="Auto Mapping"
        subtitle="Paste your API docs or a sample response and Rhesis will configure the mapping for you."
        actions={
          <Button
            variant="contained"
            startIcon={<AutoFixHighIcon />}
            onClick={() => setAutoConfigureOpen(true)}
            sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            Auto Mapping
          </Button>
        }
      />

      <EditableSection
        title="Manual Mapping"
        subtitle={
          <>
            Define the request format, run a test call, then click the response
            field that holds your model&apos;s reply.{' '}
            <Link
              href="https://docs.rhesis.ai/docs/endpoints/mapping-examples"
              target="_blank"
              rel="noopener"
            >
              See examples ↗
            </Link>
          </>
        }
        headerActions={
          <IconButton
            aria-label={
              manualExpanded
                ? 'Collapse manual mapping'
                : 'Expand manual mapping'
            }
            size="small"
            onClick={() => setManualExpanded(e => !e)}
            sx={{ color: 'primary.main' }}
          >
            {manualExpanded ? (
              <KeyboardArrowUpIcon />
            ) : (
              <KeyboardArrowDownIcon />
            )}
          </IconButton>
        }
        initialValue={mappingInitial}
        onSave={async draft => {
          let responseMapping: Record<string, string>;
          try {
            responseMapping = JSON.parse(draft.resBody);
          } catch {
            notifications.show('Invalid JSON in response mapping', {
              severity: 'error',
            });
            throw new Error('validation');
          }
          await saveFields({
            request_mapping: bodyToRequestMapping(
              draft.reqBody
            ) as unknown as Record<string, unknown>,
            response_mapping: responseMapping,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Collapse in={manualExpanded}>
            {isEditing ? (
              <MappingEditor
                requestTemplate={draft.reqBody}
                responseMapping={(() => {
                  try {
                    return JSON.parse(draft.resBody);
                  } catch {
                    return {};
                  }
                })()}
                onRequestTemplateChange={t =>
                  setDraft(prev => ({ ...prev, reqBody: t }))
                }
                onResponseMappingChange={m =>
                  setDraft(prev => ({
                    ...prev,
                    resBody: JSON.stringify(m, null, 2),
                  }))
                }
                onTest={inputData =>
                  handleRunTest(inputData, draft.reqBody, draft.resBody)
                }
                testResponse={testResponse}
                isTestingEndpoint={isTestingEndpoint}
              />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Request mapping
                  </Typography>
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      m: 0,
                      p: 2,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      overflow: 'auto',
                      fontFamily: 'monospace',
                      fontSize: 13,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {draft.reqBody || '{}'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Response mapping
                  </Typography>
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      m: 0,
                      p: 2,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      overflow: 'auto',
                      fontFamily: 'monospace',
                      fontSize: 13,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {draft.resBody || '{}'}
                  </Typography>
                </Box>
              </Box>
            )}
          </Collapse>
        )}
      </EditableSection>

      <AutoConfigureDrawer
        open={autoConfigureOpen}
        onClose={() => setAutoConfigureOpen(false)}
        onApply={result => {
          void handleAutoConfigureApply(result);
        }}
        url={endpoint.url || ''}
        authToken=""
        method={endpoint.method || 'POST'}
      />
    </Box>
  );
}
