'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import { AutoFixHighIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import TestAndMap from '../TestAndMap';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TestResult {
  success: boolean;
  status?: number;
  response?: Record<string, unknown>;
  error?: string;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface TabBodyProps {
  reqBody: string;
  resBody: string;
  onReqBodyChange: React.Dispatch<React.SetStateAction<string>>;
  onResBodyChange: React.Dispatch<React.SetStateAction<string>>;
  testResult: TestResult | null;
  isTestingEndpoint: boolean;
  onRunTest: (inputData: Record<string, unknown>) => void;
  onAutoConfigureOpen: () => void;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TabBody({
  reqBody,
  resBody,
  onReqBodyChange,
  onResBodyChange,
  testResult,
  isTestingEndpoint,
  onRunTest,
  onAutoConfigureOpen,
}: TabBodyProps) {
  // Derive testResponse string from testResult
  const testResponse = (() => {
    if (!testResult) return '';
    if (testResult.response)
      return JSON.stringify(testResult.response, null, 2);
    if (testResult.error)
      return JSON.stringify({ error: testResult.error }, null, 2);
    return '';
  })();

  // Parse resBody → responseMapping Record<string, string>
  const responseMapping: Record<string, string> = (() => {
    try {
      return JSON.parse(resBody);
    } catch {
      return {};
    }
  })();

  const handleRequestTemplateChange = (t: string) => {
    onReqBodyChange(t);
  };

  const handleResponseMappingChange = (m: Record<string, string>) => {
    onResBodyChange(JSON.stringify(m, null, 2));
  };

  return (
    <Box>
      {/* Auto-configure hero */}
      <Box
        sx={{
          border: 1,
          borderColor: 'primary.main',
          borderRadius: BORDER_RADIUS.md,
          px: 3,
          py: 2.5,
          mb: 3,
          bgcolor: theme =>
            theme.palette.mode === 'light'
              ? 'rgba(0,128,175,0.04)'
              : 'rgba(0,128,175,0.1)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <AutoFixHighIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography
            variant="subtitle2"
            sx={{ color: 'primary.main', fontWeight: 600 }}
          >
            Auto-configure
          </Typography>
        </Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Let Rhesis analyse your API and fill in request and response fields
            automatically.
          </Typography>
          <Button
            variant="contained"
            startIcon={<AutoFixHighIcon />}
            onClick={onAutoConfigureOpen}
            sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            Auto-configure
          </Button>
        </Box>
      </Box>

      {/* Map & test card */}
      <SectionCard title="Map & test">
        <TestAndMap
          requestTemplate={reqBody}
          responseMapping={responseMapping}
          onRequestTemplateChange={handleRequestTemplateChange}
          onResponseMappingChange={handleResponseMappingChange}
          onTest={onRunTest}
          testResponse={testResponse}
          isTestingEndpoint={isTestingEndpoint}
        />
      </SectionCard>
    </Box>
  );
}
