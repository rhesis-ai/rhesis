'use client';

import React, { useState } from 'react';
import { Box, Button, Collapse, Link, IconButton } from '@mui/material';
import {
  AutoFixHighIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import TestAndMap from '../TestAndMap';

interface TestResult {
  success: boolean;
  status?: number;
  response?: Record<string, unknown>;
  error?: string;
}

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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <SectionCard
        title="Auto Mapping"
        subtitle="Paste your API docs or a sample response and Rhesis will configure the mapping for you."
        actions={
          <Button
            variant="contained"
            startIcon={<AutoFixHighIcon />}
            onClick={onAutoConfigureOpen}
            sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            Auto Mapping
          </Button>
        }
      />

      <SectionCard
        title="Manual Mapping"
        subtitle={
          <>
            Define the request format, run a test call, then click the response
            field that holds your model&apos;s reply.{' '}
            <Link
              href="https://docs.rhesis.ai/docs/endpoints/mapping-examples"
              target="_blank"
              rel="noopener"
            >
              See examples ↗
            </Link>
          </>
        }
        actions={
          <IconButton
            aria-label={
              manualExpanded ? 'Collapse manual mapping' : 'Expand manual mapping'
            }
            onClick={() => setManualExpanded(e => !e)}
            size="small"
            sx={{ color: 'primary.main' }}
          >
            {manualExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        }
      >
        <Collapse in={manualExpanded}>
          <TestAndMap
            requestTemplate={reqBody}
            responseMapping={responseMapping}
            onRequestTemplateChange={handleRequestTemplateChange}
            onResponseMappingChange={handleResponseMappingChange}
            onTest={onRunTest}
            testResponse={testResponse}
            isTestingEndpoint={isTestingEndpoint}
          />
        </Collapse>
      </SectionCard>
    </Box>
  );
}
