'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Box, IconButton, Stack, Tooltip } from '@mui/material';
import { CloseIcon } from '@/components/icons';
import RequestMappingCard from './RequestMappingCard';
import ResponseMappingCard from './ResponseMappingCard';
import { HelpArticlesPanel, MappingCard, TwoCardRow } from './MappingRows';
import TestValuesEditor from './TestValuesEditor';
import {
  RawResponseCollapse,
  RunTestButton,
  type EndpointTestResult,
} from './TestResponseCard';
import {
  buildTestCurl,
  isFileVar,
  testValueVars,
  type TestValues,
} from './testValues';

const INPUT_VAR_RE = /\{\{\s*input\b/;
const OUTPUT_MAPPED_RE = /"output"\s*:\s*"[^"]+"/;
const AUTO_RUN_DELAY_MS = 800;

interface TabMappingProps {
  reqBody: string;
  resBody: string;
  onReqBodyChange: (value: string) => void;
  onResBodyChange: (value: string) => void;
  /** Values the test request sends; shared with the Test step. */
  testValues: TestValues;
  onTestValuesChange: (values: TestValues) => void;
  testResult: EndpointTestResult | null;
  isTestingEndpoint: boolean;
  /** Sends a test request with the current test values. */
  onRunTest: () => void;
  /** The last result was run against the current URL, headers, auth and request. */
  resultIsCurrent: boolean;
  /** When the running test started, for the elapsed time. */
  testStartedAt?: number | null;
  /** The last test took long, so edits no longer re-send it by themselves. */
  isSlowApi?: boolean;
  /** The longest a test can wait: the endpoint's timeout, capped by the proxy. */
  maxWaitSeconds?: number;
  onCancelTest?: () => void;
  /** For the cURL preview of the request being sent. */
  url?: string;
  method?: string;
  requestHeaders?: string;
}

export default function TabMapping({
  reqBody,
  resBody,
  onReqBodyChange,
  onResBodyChange,
  testValues,
  onTestValuesChange,
  testResult,
  isTestingEndpoint,
  onRunTest,
  resultIsCurrent,
  testStartedAt,
  isSlowApi = false,
  maxWaitSeconds,
  onCancelTest,
  url = '',
  method = 'POST',
  requestHeaders,
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
  // A slow API isn't called again on every edit; the button sends it instead.
  useEffect(() => {
    if (!inputMapped || isSlowApi || alreadyRanFor.current === reqBody) return;
    const timer = setTimeout(() => runRef.current(), AUTO_RUN_DELAY_MS);
    return () => clearTimeout(timer);
  }, [reqBody, inputMapped, isSlowApi]);

  // Files can't be picked here; the Test step has the upload.
  const textVars = useMemo(
    () => testValueVars(reqBody).filter(v => !isFileVar(v)),
    [reqBody]
  );

  const [showTestRequest, setShowTestRequest] = useState(false);
  const testRequestRef = useRef<HTMLDivElement>(null);
  // It opens from the button at the top, so bring it into view at the card's foot.
  useEffect(() => {
    if (showTestRequest) {
      testRequestRef.current?.scrollIntoView?.({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [showTestRequest]);

  const testRequestCard = textVars.length > 0 && showTestRequest && (
    <Box ref={testRequestRef} sx={{ '& > .MuiPaper-root': { mb: 0 } }}>
      <MappingCard
        title="Test request"
        action={
          <Tooltip title="Hide test request">
            <IconButton
              size="small"
              aria-label="Hide test request"
              onClick={() => setShowTestRequest(false)}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        }
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TestValuesEditor
            vars={textVars}
            values={testValues}
            onValuesChange={onTestValuesChange}
            editorKey="create-mapping-test-values"
            jsonOnly
          />
        </Box>
      </MappingCard>
    </Box>
  );

  return (
    <Stack spacing={5}>
      <TwoCardRow
        left={
          // Always this wrapper, so opening the test request doesn't remount the Request card.
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 3,
              '& > .MuiPaper-root': { mb: 0, flex: 1 },
            }}
          >
            <RequestMappingCard
              template={reqBody}
              onChange={onReqBodyChange}
              complete={requestDone}
              action={
                <RunTestButton
                  label="Send test request"
                  onRun={onRunTest}
                  menuItems={[
                    {
                      label: 'Edit test request',
                      onClick: () => setShowTestRequest(true),
                    },
                  ]}
                  isTesting={isTestingEndpoint}
                  blockedReason={
                    inputMapped ? undefined : 'Map the input variable first.'
                  }
                />
              }
            />
            {testRequestCard}
          </Box>
        }
        right={
          <ResponseMappingCard
            responseMapping={resBody}
            onResponseMappingChange={onResBodyChange}
            testResult={testResult}
            isTesting={isTestingEndpoint}
            inputMapped={inputMapped}
            complete={responseDone}
            waiting={{
              startedAt: testStartedAt,
              maxWaitSeconds,
              onCancel: onCancelTest,
              waitingDetails: (
                <RawResponseCollapse
                  label="Request being sent (cURL)"
                  value={buildTestCurl({
                    method,
                    url,
                    requestHeaders,
                    reqBody,
                    values: testValues,
                  })}
                />
              ),
            }}
            notice={
              isSlowApi &&
              !isTestingEndpoint && (
                <Alert severity="info">
                  Your API is slow, so Rhesis no longer re-sends the test after
                  every change. Click Send test request when you&apos;re ready.
                </Alert>
              )
            }
          />
        }
      />
      {!testResult?.success && <HelpArticlesPanel />}
    </Stack>
  );
}
