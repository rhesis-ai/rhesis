'use client';

import { useMemo } from 'react';
import { Typography } from '@mui/material';
import { useNotifications } from '@/components/common/NotificationContext';
import EditableSection from '@/components/common/EditableSection';
import { useEndpointDetailContext } from './EndpointDetailContext';
import JsonMonacoField from './JsonMonacoField';

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
  const isSdk = endpoint.connection_type === 'SDK';

  const headersInitial = useMemo(
    () => JSON.stringify(endpoint.request_headers || {}, null, 2),
    [endpoint.request_headers]
  );

  const notifyError = (msg: string) => {
    notifications.show(msg, { severity: 'error' });
  };

  if (isSdk) return null;

  return (
    <EditableSection
      title="Request headers"
      initialValue={headersInitial}
      onSave={async draft => {
        const parsed = parseStringRecord(draft, 'Request headers', notifyError);
        await saveFields({ request_headers: parsed });
      }}
    >
      {({ draft, setDraft, isEditing }) => (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Custom headers for your endpoint. Authorization and Content-Type are
            provided automatically. Example:{' '}
            <code>{`{ "x-api-key": "{{ auth_token }}" }`}</code>
          </Typography>
          <JsonMonacoField
            editorKey="request-headers"
            height="200px"
            theme={editorTheme}
            wrapperSx={editorWrapperStyle}
            readOnly={!isEditing}
            value={draft}
            onChange={setDraft}
          />
        </>
      )}
    </EditableSection>
  );
}
