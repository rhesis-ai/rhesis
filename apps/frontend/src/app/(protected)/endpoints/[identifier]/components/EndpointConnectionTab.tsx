'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { normalizeUrl } from '@/utils/validation';
import { useNotifications } from '@/components/common/NotificationContext';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { METHODS } from './endpoint-detail-shared';
import { detailGridSpacing } from './endpoint-overview-utils';
import EndpointSdkConnectionPanel from './EndpointSdkConnectionPanel';
import EndpointHeadersFields from '../../components/EndpointHeadersFields';

interface RestConnectionDraft {
  url: string;
  method: string;
}

interface HeadersDraft {
  auth_token: string;
  request_headers: string;
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
  const notifications = useNotifications();
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [tokenFieldFocused, setTokenFieldFocused] = useState(false);

  const restInitial = useMemo(
    () => ({ url: endpoint.url || '', method: endpoint.method || 'POST' }),
    [endpoint.url, endpoint.method]
  );

  const headersInitial = useMemo<HeadersDraft>(
    () => ({
      auth_token: '',
      request_headers: JSON.stringify(endpoint.request_headers || {}, null, 2),
    }),
    [endpoint.request_headers]
  );

  if (endpoint.connection_type === 'SDK') {
    return <EndpointSdkConnectionPanel />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <EditableSection<RestConnectionDraft>
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
            columnSpacing={detailGridSpacing.columnSpacing(isEditing)}
            rowSpacing={detailGridSpacing.rowSpacing(isEditing)}
          >
            <Grid size={{ xs: 12, md: 8 }}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="URL"
                  placeholder="api.example.com or https://api.example.com"
                  helperText="https:// will be added automatically if omitted"
                  value={draft.url}
                  onChange={e =>
                    setDraft(prev => ({ ...prev, url: e.target.value }))
                  }
                />
              ) : (
                <ViewField label="URL" value={endpoint.url || '—'} />
              )}
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
        title="Authentication & headers"
        initialValue={headersInitial}
        isDirty={(draft, initial) =>
          draft.request_headers !== initial.request_headers ||
          draft.auth_token.trim() !== ''
        }
        onSave={async draft => {
          const parsed = parseStringRecord(
            draft.request_headers,
            'Request headers',
            msg => notifications.show(msg, { severity: 'error' })
          );
          const payload: {
            request_headers: Record<string, string>;
            auth_token?: string;
          } = { request_headers: parsed };
          if (draft.auth_token.trim()) payload.auth_token = draft.auth_token;
          await saveFields(payload);
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <EndpointHeadersFields
            authToken={draft.auth_token}
            requestHeaders={draft.request_headers}
            onAuthTokenChange={value =>
              setDraft(prev => ({ ...prev, auth_token: value }))
            }
            onRequestHeadersChange={value =>
              setDraft(prev => ({ ...prev, request_headers: value }))
            }
            showAuthToken={showAuthToken}
            onToggleAuthToken={() => setShowAuthToken(v => !v)}
            editorTheme={editorTheme}
            isEditing={isEditing}
            hasExistingToken={Boolean(endpoint.id)}
            tokenFieldFocused={tokenFieldFocused}
            onTokenFocus={() => {
              setTokenFieldFocused(true);
              if (draft.auth_token === '') {
                setDraft(prev => ({ ...prev, auth_token: '' }));
              }
            }}
            onTokenBlur={() => {
              if (draft.auth_token === '') setTokenFieldFocused(false);
            }}
            editorWrapperStyle={editorWrapperStyle}
          />
        )}
      </EditableSection>
    </Box>
  );
}
