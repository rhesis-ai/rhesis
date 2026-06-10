'use client';

import React, { useState } from 'react';
import { Box, Button, Collapse, Link, Typography } from '@mui/material';
import {
  AutoFixHighIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { alpha } from '@mui/material/styles';
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
  const [manualExpanded, setManualExpanded] = useState(false);

  const testResponse = (() => {
    if (!testResult) return '';
    if (testResult.response)
      return JSON.stringify(testResult.response, null, 2);
    if (testResult.error)
      return JSON.stringify({ error: testResult.error }, null, 2);
    return '';
  })();

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

  const panelSx = {
    border: 1,
    borderColor: 'primary.main',
    borderRadius: BORDER_RADIUS.md,
    px: 3,
    py: 2.5,
    mb: 3,
    bgcolor: (theme: {
      palette: { mode: string; primary: { main: string } };
    }) =>
      theme.palette.mode === 'light'
        ? alpha(theme.palette.primary.main, 0.04)
        : alpha(theme.palette.primary.main, 0.1),
  };

  return (
    <Box>
      {/* Auto Mapping */}
      <Box sx={panelSx}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <AutoFixHighIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography
            variant="subtitle2"
            sx={{ color: 'primary.main', fontWeight: 600 }}
          >
            Auto Mapping
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
            Auto Mapping
          </Button>
        </Box>
      </Box>

      {/* Manual Mapping — collapsible */}
      <Box
        sx={{
          border: 1,
          borderColor: 'divider',
          borderRadius: BORDER_RADIUS.md,
          px: 3,
          py: 2.5,
          mb: 3,
          bgcolor: 'background.paper',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            mb: manualExpanded ? 0.5 : 0,
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{ color: 'primary.main', fontWeight: 600, flex: 1 }}
          >
            Manual Mapping
          </Typography>
          <Box
            onClick={() => setManualExpanded(e => !e)}
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
          >
            {manualExpanded ? (
              <KeyboardArrowUpIcon
                sx={{ fontSize: 20, color: 'primary.main' }}
              />
            ) : (
              <KeyboardArrowDownIcon
                sx={{ fontSize: 20, color: 'primary.main' }}
              />
            )}
          </Box>
        </Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            cursor: 'pointer',
          }}
          onClick={() => setManualExpanded(e => !e)}
        >
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Tell Rhesis how to call your API and where to find the answer.
            Define the request format once, fire a test call, then click the
            field in the response that contains your model&apos;s reply.{' '}
            <Link
              href="https://docs.rhesis.ai/docs/endpoints/mapping-examples"
              target="_blank"
              rel="noopener"
              onClick={e => e.stopPropagation()}
            >
              See examples ↗
            </Link>
          </Typography>
        </Box>

        <Collapse in={manualExpanded}>
          <Box sx={{ mt: 2.5 }}>
            <TestAndMap
              requestTemplate={reqBody}
              responseMapping={responseMapping}
              onRequestTemplateChange={handleRequestTemplateChange}
              onResponseMappingChange={handleResponseMappingChange}
              onTest={onRunTest}
              testResponse={testResponse}
              isTestingEndpoint={isTestingEndpoint}
            />
          </Box>
        </Collapse>
      </Box>
    </Box>
  );
}
