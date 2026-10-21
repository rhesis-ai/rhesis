'use client';

import React from 'react';
import { Box, Stack, TextField } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import EndpointHeadersFields from './EndpointHeadersFields';
import type { FormData } from './EndpointForm';

function validateUrl(url: string) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

interface TabConnectionProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
}

export default function TabConnection({
  formData,
  onChange,
}: TabConnectionProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';
  const urlInvalid = Boolean(formData.url && !validateUrl(formData.url));

  return (
    <Stack spacing={5}>
      <Box sx={{ display: 'flex', gap: 3.75 }}>
        <TextField
          label="Method"
          value={formData.method}
          onChange={e => onChange('method', e.target.value)}
          slotProps={{ input: { readOnly: true } }}
          sx={{ flex: 1 }}
        />
        <TextField
          required
          name="url"
          label="Endpoint URL"
          value={formData.url}
          onChange={e => onChange('url', e.target.value)}
          placeholder="https://api.example.com/chat"
          error={urlInvalid}
          helperText={urlInvalid ? 'Enter a valid URL' : undefined}
          sx={{ flex: 3 }}
        />
      </Box>

      <Box>
        <Box sx={{ mb: 3 }}>
          <FormSectionDivider
            headline="Authentication"
            descriptiveText="Configure the credentials Rhesis sends with each request."
          />
        </Box>
        <EndpointHeadersFields
          authType={formData.auth_type}
          onAuthTypeChange={v => onChange('auth_type', v)}
          clientCredentials={formData.client_credentials}
          onClientCredentialsChange={v => onChange('client_credentials', v)}
          authToken={formData.auth_token}
          requestHeaders={formData.request_headers}
          onAuthTokenChange={v => onChange('auth_token', v)}
          onRequestHeadersChange={v => onChange('request_headers', v)}
          editorTheme={editorTheme}
          isEditing
          easyHeaderInput
        />
      </Box>
    </Stack>
  );
}
