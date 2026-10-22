'use client';

import React, { useEffect, useRef } from 'react';
import { Stack } from '@mui/material';
import RequestMappingCard from './RequestMappingCard';
import ResponseMappingCard from './ResponseMappingCard';
import { HelpArticlesPanel, TwoCardRow } from './MappingRows';
import { RunTestButton, type EndpointTestResult } from './TestResponseCard';

const INPUT_VAR_RE = /\{\{\s*input\b/;
const OUTPUT_MAPPED_RE = /"output"\s*:\s*"[^"]+"/;
const AUTO_RUN_DELAY_MS = 800;

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
  /** The last result was run against the current URL, headers, auth and request. */
  resultIsCurrent: boolean;
}

export default function TabMapping({
  reqBody,
  resBody,
  onReqBodyChange,
  onResBodyChange,
  testResult,
  isTestingEndpoint,
  onRunTest,
  resultIsCurrent,
}: TabMappingProps) {
  const inputMapped = INPUT_VAR_RE.test(reqBody);
  // Green means done: the request once its test passed for this mapping, the
  // response once output is mapped too (the same rule that unlocks Next).
  const requestDone = Boolean(testResult?.success) && resultIsCurrent;
  const responseDone = requestDone && OUTPUT_MAPPED_RE.test(resBody);

  // Latest callback, so a delayed run tests the setup as it is when it fires.
  const runRef = useRef(onRunTest);
  runRef.current = onRunTest;
  // Coming back to a step whose result is still current keeps it instead of re-running.
  const alreadyRanFor = useRef(resultIsCurrent ? reqBody : null);

  // Send the test as soon as the request is mapped, and again after each edit,
  // so the response is there to map without hunting for a button.
  useEffect(() => {
    if (!inputMapped || alreadyRanFor.current === reqBody) return;
    const timer = setTimeout(
      () => runRef.current(MAPPING_TEST_INPUT),
      AUTO_RUN_DELAY_MS
    );
    return () => clearTimeout(timer);
  }, [reqBody, inputMapped]);

  return (
    <Stack spacing={5}>
      <TwoCardRow
        left={
          <RequestMappingCard
            template={reqBody}
            onChange={onReqBodyChange}
            complete={requestDone}
            action={
              <RunTestButton
                label="Send test request"
                onRun={() => onRunTest(MAPPING_TEST_INPUT)}
                isTesting={isTestingEndpoint}
                blockedReason={
                  inputMapped ? undefined : 'Map the input variable first.'
                }
              />
            }
          />
        }
        right={
          <ResponseMappingCard
            responseMapping={resBody}
            onResponseMappingChange={onResBodyChange}
            testResult={testResult}
            isTesting={isTestingEndpoint}
            inputMapped={inputMapped}
            complete={responseDone}
          />
        }
      />
      {!testResult?.success && <HelpArticlesPanel />}
    </Stack>
  );
}
