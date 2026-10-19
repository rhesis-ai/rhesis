'use client';

import { useMemo } from 'react';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  Box,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
} from '@mui/material';
import { SECTION_GRID } from '@/styles/theme-constants';
import EditableSection from '@/components/common/EditableSection';
import EditableField from '@/components/common/EditableField';
import ViewField from '@/components/common/ViewField';
import { normalizeUrl } from '@/utils/validation';
import { useNotifications } from '@/components/common/NotificationContext';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { METHODS } from './endpoint-detail-shared';
import EndpointSdkConnectionPanel from './EndpointSdkConnectionPanel';
import EndpointHeadersFields from '../../components/EndpointHeadersFields';
import {
  ENDPOINT_AUTH_TYPES,
  type EndpointAuthType,
} from '@/constants/endpoint-auth';
import type { EndpointEditData } from '@/utils/api-client/interfaces/endpoint';
import {
  authPayload,
  authTypeOf,
  clientCredentialsFromEndpoint,
  validateClientCredentials,
  type ClientCredentialsDraft,
} from '../../components/endpointAuth';

interface RestConnectionDraft {
  url: string;
  method: string;
}

interface HeadersDraft {
  auth_type: EndpointAuthType;
  client_credentials: ClientCredentialsDraft;
  auth_token: string;
  request_headers: string;
  // true when the user explicitly removed the saved token
  clear_token: boolean;
}

function parseStringRecord(
  value: string,
  fieldLabel: string,
  notify: (msg: string) => void
): Record<string, string> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    notify(`Invalid JSON in ${fieldLabel}`);
    throw new Error('validation');
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    notify(`${fieldLabel} must be a JSON object`);
    throw new Error('validation');
  }
  for (const [key, entry] of Object.entries(
    parsed as Record<string, unknown>
  )) {
    if (typeof entry !== 'string') {
      notify(`${fieldLabel}: "${key}" must be a string value`);
      throw new Error('validation');
    }
  }
  return parsed as Record<string, string>;
}

export default function EndpointConnectionTab() {
  const { endpoint, editorTheme, editorWrapperStyle, saveFields } =
    useEndpointDetailContext();
  const canEditEndpoint = useCan(Capability.Endpoint.UPDATE);
  const notifications = useNotifications();

  const restInitial = useMemo(
    () => ({ url: endpoint.url || '', method: endpoint.method || 'POST' }),
    [endpoint.url, endpoint.method]
  );

  const headersInitial = useMemo<HeadersDraft>(
    () => ({
      auth_type: authTypeOf(endpoint),
      client_credentials: clientCredentialsFromEndpoint(endpoint),
      auth_token: '',
      request_headers: JSON.stringify(endpoint.request_headers || {}, null, 2),
      clear_token: false,
    }),
    [endpoint]
  );
  const hasStoredClientSecret = Boolean(endpoint.has_client_secret);

  if (endpoint.connection_type === 'SDK') {
    return <EndpointSdkConnectionPanel />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <EditableSection<RestConnectionDraft>
        editable={canEditEndpoint}
        title="REST connection"
        initialValue={restInitial}
        onSave={async draft => {
          await saveFields({
            url: normalizeUrl(draft.url),
            method: draft.method,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid
            container
            columnSpacing={SECTION_GRID.columnSpacing}
            rowSpacing={SECTION_GRID.rowSpacing}
          >
            <Grid size={{ xs: 12, md: 8 }}>
              <EditableField
                fullWidth
                editing={isEditing}
                label="URL"
                placeholder={
                  isEditing
                    ? 'api.example.com or https://api.example.com'
                    : undefined
                }
                helperText={
                  isEditing
                    ? 'https:// will be added automatically if omitted'
                    : undefined
                }
                value={isEditing ? draft.url : endpoint.url || '—'}
                onChange={e =>
                  setDraft(prev => ({ ...prev, url: e.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Method</InputLabel>
                  <Select
                    value={draft.method}
                    label="Method"
                    onChange={e =>
                      setDraft(prev => ({ ...prev, method: e.target.value }))
                    }
                  >
                    {METHODS.map(method => (
                      <MenuItem key={method} value={method}>
                        {method}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <ViewField label="Method" value={endpoint.method || '—'} />
              )}
            </Grid>
            <Grid size={12}>
              <ViewField
                label="Connection type"
                value={endpoint.connection_type}
              />
            </Grid>
          </Grid>
        )}
      </EditableSection>

      <EditableSection
        editable={canEditEndpoint}
        title="Authentication & headers"
        initialValue={headersInitial}
        isDirty={(draft, initial) =>
          draft.request_headers !== initial.request_headers ||
          draft.auth_type !== initial.auth_type ||
          JSON.stringify(draft.client_credentials) !==
            JSON.stringify(initial.client_credentials) ||
          draft.auth_token.trim() !== '' ||
          draft.clear_token
        }
        onSave={async draft => {
          const parsed = parseStringRecord(
            draft.request_headers,
            'Request headers',
            msg => notifications.show(msg, { severity: 'error' })
          );
          const isClientCredentials =
            draft.auth_type === ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS;
          if (isClientCredentials) {
            const authError = validateClientCredentials(
              draft.client_credentials,
              hasStoredClientSecret
            );
            if (authError) {
              notifications.show(authError, { severity: 'error' });
              throw new Error('validation');
            }
          }
          const payload: EndpointEditData = {
            request_headers: parsed,
            ...authPayload(draft.auth_type, draft.client_credentials),
          };
          if (!isClientCredentials && draft.auth_token.trim()) {
            payload.auth_token = draft.auth_token;
          } else if (!isClientCredentials && draft.clear_token) {
            payload.auth_token = null;
          }
          await saveFields(payload);
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <EndpointHeadersFields
            authType={draft.auth_type}
            onAuthTypeChange={value =>
              setDraft(prev => ({ ...prev, auth_type: value }))
            }
            clientCredentials={draft.client_credentials}
            onClientCredentialsChange={value =>
              setDraft(prev => ({ ...prev, client_credentials: value }))
            }
            hasExistingClientSecret={hasStoredClientSecret}
            authToken={draft.auth_token}
            requestHeaders={draft.request_headers}
            onAuthTokenChange={value =>
              setDraft(prev => ({
                ...prev,
                auth_token: value,
                clear_token: value.trim() !== '' ? false : prev.clear_token,
              }))
            }
            onRequestHeadersChange={value =>
              setDraft(prev => ({ ...prev, request_headers: value }))
            }
            editorTheme={editorTheme}
            isEditing={isEditing}
            hasExistingToken={Boolean(endpoint.has_auth_token)}
            tokenCleared={draft.clear_token}
            onToggleTokenCleared={() =>
              setDraft(prev => ({
                ...prev,
                clear_token: !prev.clear_token,
                auth_token: '',
              }))
            }
            editorWrapperStyle={editorWrapperStyle}
          />
        )}
      </EditableSection>
    </Box>
  );
}
