'use client';

import React from 'react';
import { Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { SectionCard } from '@/components/common/SectionCard';
import EndpointHeadersFields from '../EndpointHeadersFields';
import type { FormData } from '../EndpointForm';

interface TabHeadersProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
  showAuthToken: boolean;
  onToggleAuthToken: () => void;
}

export default function TabHeaders({
  formData,
  onChange,
  showAuthToken,
  onToggleAuthToken,
}: TabHeadersProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  return (
    <Box>
      <SectionCard
        title="Authentication & headers"
        subtitle="Configure the API token and any custom headers Rhesis should send with each request."
      >
        <EndpointHeadersFields
          authToken={formData.auth_token}
          requestHeaders={formData.request_headers}
          onAuthTokenChange={v => onChange('auth_token', v)}
          onRequestHeadersChange={v => onChange('request_headers', v)}
          showAuthToken={showAuthToken}
          onToggleAuthToken={onToggleAuthToken}
          editorTheme={editorTheme}
          isEditing
        />
      </SectionCard>
    </Box>
  );
}
