'use client';

import { useMemo, useState } from 'react';
import { useNotifications } from '@/components/common/NotificationContext';
import EditableSection from '@/components/common/EditableSection';
import EndpointHeadersFields from '../../components/EndpointHeadersFields';
import { useEndpointDetailContext } from './EndpointDetailContext';

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

export default function EndpointHeadersTab() {
  const { endpoint, editorTheme, editorWrapperStyle, saveFields } =
    useEndpointDetailContext();
  const notifications = useNotifications();
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [tokenFieldFocused, setTokenFieldFocused] = useState(false);
  const isSdk = endpoint.connection_type === 'SDK';

  const headersInitial = useMemo<HeadersDraft>(
    () => ({
      auth_token: '',
      request_headers: JSON.stringify(endpoint.request_headers || {}, null, 2),
    }),
    [endpoint.request_headers]
  );

  const notifyError = (msg: string) => {
    notifications.show(msg, { severity: 'error' });
  };

  if (isSdk) return null;

  return (
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
          notifyError
        );
        const payload: {
          request_headers: Record<string, string>;
          auth_token?: string;
        } = { request_headers: parsed };
        if (draft.auth_token.trim()) {
          payload.auth_token = draft.auth_token;
        }
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
            if (draft.auth_token === '') {
              setTokenFieldFocused(false);
            }
          }}
          editorWrapperStyle={editorWrapperStyle}
        />
      )}
    </EditableSection>
  );
}
