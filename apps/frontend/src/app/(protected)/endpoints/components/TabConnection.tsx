'use client';

import React, { useState } from 'react';
import { Box, Grid, TextField } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { SectionCard } from '@/components/common/SectionCard';
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
  const [showAuthToken, setShowAuthToken] = useState(false);

  return (
    <Box>
      <SectionCard
        title="Connection"
        subtitle="Enter the API URL of the AI application you want to test. Rhesis will send test prompts to this endpoint and evaluate how it responds."
      >
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 3, md: 2 }}>
            <TextField
              fullWidth
              label="Method"
              value={formData.method}
              onChange={e => onChange('method', e.target.value)}
              slotProps={{
                input: {
                  readOnly: true,
                  sx: { fontFamily: 'monospace', fontWeight: 700 },
                },
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 9, md: 10 }}>
            <TextField
              fullWidth
              required
              name="url"
              label="Endpoint URL"
              value={formData.url}
              onChange={e => onChange('url', e.target.value)}
              placeholder="https://api.example.com/chat"
              error={Boolean(formData.url && !validateUrl(formData.url))}
              helperText={
                formData.url && !validateUrl(formData.url)
                  ? 'Enter a valid URL'
                  : undefined
              }
            />
          </Grid>
        </Grid>

        <FormSectionDivider
          headline="Authentication & headers"
          descriptiveText="Configure the API token and any custom headers Rhesis should send with each request."
        />

        <Box sx={{ mt: 2 }}>
          <EndpointHeadersFields
            authToken={formData.auth_token}
            requestHeaders={formData.request_headers}
            onAuthTokenChange={v => onChange('auth_token', v)}
            onRequestHeadersChange={v => onChange('request_headers', v)}
            showAuthToken={showAuthToken}
            onToggleAuthToken={() => setShowAuthToken(v => !v)}
            editorTheme={editorTheme}
            isEditing
          />
        </Box>
      </SectionCard>
    </Box>
  );
}
