'use client';

import { useMemo } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { useNotifications } from '@/components/common/NotificationContext';
import EditableSection from '@/components/common/EditableSection';
import { useEndpointDetailContext } from './EndpointDetailContext';
import JsonMonacoField from './JsonMonacoField';
import { variableChipSx } from '../../components/endpoint-styles';

function parseStringRecordJsonField(
  value: string,
  fieldLabel: string,
  notify: (msg: string) => void
): Record<string, string> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
    if (
      parsed === null ||
      typeof parsed !== 'object' ||
      Array.isArray(parsed)
    ) {
      throw new Error(`${fieldLabel} must be a JSON object`);
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : `Invalid JSON in ${fieldLabel}`;
    notify(message);
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

export default function EndpointMappingsTab() {
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
                are provided automatically. Use{' '}
                <Box
                  component="span"
                  sx={{
                    display: 'inline-flex',
                    verticalAlign: 'middle',
                    mx: 0.5,
                  }}
                >
                  <Chip
                    label="{{ auth_token }}"
                    size="small"
                    sx={{
                      ...variableChipSx,
                      height: 20,
                      '& .MuiChip-label': { px: 0.75 },
                    }}
                  />
                </Box>{' '}
                to reference your API token in a header value.
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
    </>
  );
}
