'use client';

import { useEffect, useState } from 'react';
import type { TraceDetailResponse } from '@/utils/api-client/interfaces/telemetry';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { DeletedEntityData } from '@/components/common/DeletedEntityAlert';
import {
  getDeletedEntityData,
  isDeletedEntityError,
} from '@/utils/entity-error-handler';

export interface TraceTestResultState {
  testResult: TestResultDetail | null;
  loading: boolean;
  error: string | null;
  deleted: DeletedEntityData | null;
}

/** The test result a trace ran for, or nothing for a trace outside a test run. */
export function useTraceTestResult(
  trace: TraceDetailResponse
): TraceTestResultState {
  const testResultId = trace.test_result?.id;
  const [state, setState] = useState<TraceTestResultState>({
    testResult: null,
    loading: !!testResultId,
    error: null,
    deleted: null,
  });

  useEffect(() => {
    if (!testResultId) {
      setState({
        testResult: null,
        loading: false,
        error: null,
        deleted: null,
      });
      return;
    }
    let cancelled = false;
    setState({ testResult: null, loading: true, error: null, deleted: null });

    new ApiClientFactory()
      .getTestResultsClient()
      .getTestResult(testResultId)
      .then(testResult => {
        if (!cancelled)
          setState({ testResult, loading: false, error: null, deleted: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (isDeletedEntityError(err)) {
          setState({
            testResult: null,
            loading: false,
            error: null,
            deleted: getDeletedEntityData(err) ?? {
              model_name: 'TestResult',
              model_name_display: 'Test Result',
              item_id: testResultId,
              table_name: 'test_result',
              restore_url: `/recycle/test_result/${testResultId}/restore`,
              message: 'The test for this trace no longer exists.',
            },
          });
        } else {
          console.error('Failed to fetch test result:', err);
          setState({
            testResult: null,
            loading: false,
            error:
              err instanceof Error
                ? err.message
                : 'Failed to fetch test result details',
            deleted: null,
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [testResultId]);

  return state;
}
