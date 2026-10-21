'use client';

import React from 'react';
import { Box } from '@mui/material';
import RequestMappingCard from './RequestMappingCard';
import ResponseMappingCard from './ResponseMappingCard';
import { HelpArticlesPanel } from './MappingRows';
import type { EndpointTestResult } from './TestResponseCard';

const INPUT_VAR_RE = /\{\{\s*input\b/;

// The mapping check only needs a prompt; the Test step lets you choose your own.
const MAPPING_TEST_INPUT = { input: 'Hello, how are you?' };

interface TabMappingProps {
  reqBody: string;
  resBody: string;
  onReqBodyChange: (value: string) => void;
  onResBodyChange: (value: string) => void;
  testResult: EndpointTestResult | null;
  isTestingEndpoint: boolean;
  onRunTest: (inputData: Record<string, unknown>) => void;
}

export default function TabMapping({
  reqBody,
  resBody,
  onReqBodyChange,
  onResBodyChange,
  testResult,
  isTestingEndpoint,
  onRunTest,
}: TabMappingProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
        gap: 3,
        alignItems: 'start',
      }}
    >
      <RequestMappingCard template={reqBody} onChange={onReqBodyChange} />
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <ResponseMappingCard
          responseMapping={resBody}
          onResponseMappingChange={onResBodyChange}
          testResult={testResult}
          isTesting={isTestingEndpoint}
          onRunTest={() => onRunTest(MAPPING_TEST_INPUT)}
          blockedReason={
            INPUT_VAR_RE.test(reqBody)
              ? undefined
              : 'Map the input variable to a field first.'
          }
        />
        {!testResult?.success && <HelpArticlesPanel />}
      </Box>
    </Box>
  );
}
