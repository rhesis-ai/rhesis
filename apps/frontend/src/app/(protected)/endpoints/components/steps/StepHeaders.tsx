'use client';

import React from 'react';
import {
  Box,
  TextField,
  Typography,
  IconButton,
  InputAdornment,
  Button,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { SectionCard } from '@/components/common/SectionCard';
import ActionBar from '@/components/common/ActionBar';
import HeadersEditor from '../HeadersEditor';
import {
  LockIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';
import type { FormData } from '../EndpointForm';

interface StepHeadersProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
  showAuthToken: boolean;
  onToggleAuthToken: () => void;
  onNext: () => void;
  onBack: () => void;
}

export default function StepHeaders({
  formData,
  onChange,
  showAuthToken,
  onToggleAuthToken,
  onNext,
  onBack,
}: StepHeadersProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  return (
    <Box>
      <SectionCard
        title="Authentication & headers"
        subtitle="Configure the API token and any custom headers Rhesis should send with each request."
      >
        <TextField
          fullWidth
          label="API Token (optional)"
          type={showAuthToken ? 'text' : 'password'}
          value={formData.auth_token}
          onChange={e => onChange('auth_token', e.target.value)}
          placeholder="sk-..."
          sx={{ mb: 3 }}
          helperText="Added automatically as Authorization: Bearer in the request headers."
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <LockIcon color="action" />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={onToggleAuthToken} edge="end">
                  {showAuthToken ? <VisibilityOffIcon /> : <VisibilityIcon />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mb: 1 }}
        >
          Custom headers
        </Typography>
        <HeadersEditor
          authToken={formData.auth_token}
          customHeaders={formData.request_headers}
          onChange={v => onChange('request_headers', v)}
          editorTheme={editorTheme}
        />
      </SectionCard>

      <ActionBar
        leftButton={{ label: '← Back', onClick: onBack, variant: 'outlined' }}
        rightButton={{ label: 'Next →', onClick: onNext, variant: 'contained' }}
      />
    </Box>
  );
}
