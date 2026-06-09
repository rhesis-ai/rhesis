'use client';

import { useMemo } from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import { InfoIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import EditableSection from '@/components/common/EditableSection';
import { useEndpointDetailContext } from './EndpointDetailContext';
import JsonMonacoField from './JsonMonacoField';

const DOCS_URL = 'https://docs.rhesis.ai/endpoints/request-response-mapping';

function MappingHelp({
  tooltip,
  ariaLabel,
}: {
  tooltip: string;
  ariaLabel: string;
}) {
  return (
    <Tooltip title={tooltip} placement="top">
      <IconButton
        size="small"
        aria-label={ariaLabel}
        sx={{ ml: 0.5, color: 'text.secondary' }}
      >
        <InfoIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}

function parseJsonField(
  value: string,
  fieldLabel: string,
  notify: (msg: string) => void
): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    if (
      parsed === null ||
      typeof parsed !== 'object' ||
      Array.isArray(parsed)
    ) {
      throw new Error(`${fieldLabel} must be a JSON object`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    const message =
      error instanceof Error ? error.message : `Invalid JSON in ${fieldLabel}`;
    notify(message);
    throw new Error('validation');
  }
}

function parseStringRecordJsonField(
  value: string,
  fieldLabel: string,
  notify: (msg: string) => void
): Record<string, string> {
  const parsed = parseJsonField(value, fieldLabel, notify);
  for (const [key, entry] of Object.entries(parsed)) {
    if (typeof entry !== 'string') {
      notify(`${fieldLabel}: "${key}" must be a string value`);
      throw new Error('validation');
    }
  }
  return parsed as Record<string, string>;
}

export default function EndpointMappingsTab() {
  const { endpoint, editorTheme, editorWrapperStyle, saveFields } =
    useEndpointDetailContext();
  const notifications = useNotifications();
  const isSdk = endpoint.connection_type === 'SDK';

  const headersInitial = useMemo(
    () => JSON.stringify(endpoint.request_headers || {}, null, 2),
    [endpoint.request_headers]
  );
  const requestMappingInitial = useMemo(
    () => JSON.stringify(endpoint.request_mapping || {}, null, 2),
    [endpoint.request_mapping]
  );
  const responseMappingInitial = useMemo(
    () => JSON.stringify(endpoint.response_mapping || {}, null, 2),
    [endpoint.response_mapping]
  );

  const notifyError = (msg: string) => {
    notifications.show(msg, { severity: 'error' });
  };

  return (
    <>
      {!isSdk && (
        <EditableSection
          title="Request headers"
          initialValue={headersInitial}
          onSave={async draft => {
            const parsed = parseStringRecordJsonField(
              draft,
              'Request headers',
              notifyError
            );
            await saveFields({ request_headers: parsed });
          }}
        >
          {({ draft, setDraft, isEditing }) => (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Custom headers for your endpoint. Authorization and Content-Type
                are provided automatically. Example:{' '}
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
      )}

      <EditableSection
        title="Request mapping"
        initialValue={requestMappingInitial}
        onSave={async draft => {
          const parsed = parseJsonField(draft, 'Request mapping', notifyError);
          await saveFields({ request_mapping: parsed });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Maps Rhesis test fields to your endpoint&apos;s request body.
                Use <code>{'{{ field }}'}</code> placeholders.
              </Typography>
              <MappingHelp
                ariaLabel="Request mapping help"
                tooltip={`Maps prompt and context fields from Rhesis tests to your endpoint body. See ${DOCS_URL}`}
              />
            </Box>
            <JsonMonacoField
              editorKey="request-mapping"
              height="360px"
              theme={editorTheme}
              wrapperSx={editorWrapperStyle}
              readOnly={!isEditing}
              value={draft}
              onChange={setDraft}
            />
          </>
        )}
      </EditableSection>

      <EditableSection
        title="Response mapping"
        initialValue={responseMappingInitial}
        onSave={async draft => {
          const parsed = parseJsonField(draft, 'Response mapping', notifyError);
          await saveFields({ response_mapping: parsed });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Maps your endpoint&apos;s response fields back to Rhesis. Must
                include a <code>response</code> key.
              </Typography>
              <MappingHelp
                ariaLabel="Response mapping help"
                tooltip={`Maps fields from your endpoint's JSON response to Rhesis result fields. See ${DOCS_URL}`}
              />
            </Box>
            <JsonMonacoField
              editorKey="response-mapping"
              height="280px"
              theme={editorTheme}
              wrapperSx={editorWrapperStyle}
              readOnly={!isEditing}
              value={draft}
              onChange={setDraft}
            />
          </>
        )}
      </EditableSection>
    </>
  );
}
