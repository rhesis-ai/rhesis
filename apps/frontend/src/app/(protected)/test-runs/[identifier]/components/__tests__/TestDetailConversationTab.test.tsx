import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import TestDetailConversationTab from '../TestDetailConversationTab';
import type {
  ConversationTurn,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

// ---- Stub children: only the summary handed to ConversationHistory matters ----

let lastSummary: ConversationTurn[] = [];

jest.mock('@/components/common/ConversationHistory', () => ({
  __esModule: true,
  default: ({
    conversationSummary,
  }: {
    conversationSummary: ConversationTurn[];
  }) => {
    lastSummary = conversationSummary;
    return null;
  },
}));

jest.mock('@/app/(protected)/traces/components/TraceDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({
      listTraces: jest.fn().mockResolvedValue({ traces: [] }),
    }),
    getFilesClient: () => ({ getSpanFiles: jest.fn().mockResolvedValue([]) }),
  })),
}));

// ---- Fixtures ----

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

// Single-turn result: passing metric, and no goal_evaluation (multi-turn only).
const makeSingleTurnResult = (
  overrides: Partial<TestResultDetail> = {}
): TestResultDetail =>
  ({
    id: u(1),
    execution: 'ok',
    verdict: 'pass',
    test_metrics: {
      execution_time: 100,
      metrics: {
        'Non-English Deferral Compliance': {
          score: 'Compliant Deferral',
          reason: 'Refused in English and did not answer the request.',
          backend: 'custom',
          description: '',
          is_successful: true,
        },
      },
    },
    test_output: { output: 'I am only able to provide assistance in English.' },
    test: { prompt: { content: 'Pouvez-vous me donner des conseils ?' } },
    status: { id: u(10), name: 'Pass' },
    ...overrides,
  }) as unknown as TestResultDetail;

// ---- Tests ----

describe('TestDetailConversationTab — single-turn turn status', () => {
  beforeEach(() => {
    lastSummary = [];
  });

  it('marks the turn passed when the result passed', () => {
    render(<TestDetailConversationTab test={makeSingleTurnResult()} />);

    expect(lastSummary).toHaveLength(1);
    expect(lastSummary[0].success).toBe(true);
  });

  it('marks the turn failed when a metric failed', () => {
    const test = makeSingleTurnResult({
      execution: 'ok',
      verdict: 'fail',
      test_metrics: {
        execution_time: 100,
        metrics: {
          'Non-English Deferral Compliance': {
            score: 'Answered Anyway',
            reason: 'Answered the request in French.',
            backend: 'custom',
            description: '',
            is_successful: false,
          },
        },
      },
      status: { id: u(11), name: 'Fail' },
    } as unknown as Partial<TestResultDetail>);

    render(<TestDetailConversationTab test={test} />);

    expect(lastSummary[0].success).toBe(false);
  });

  it('follows a human review that overrides a failed result', () => {
    // The backend applies and persists a test-level review's verdict
    // synchronously (see services/review_override.py), so a reviewed
    // result's execution/verdict already reflect the override by the time
    // the client has it -- the raw is_successful=false metric stays as the
    // pre-review record.
    const test = makeSingleTurnResult({
      execution: 'ok',
      verdict: 'pass',
      test_metrics: {
        execution_time: 100,
        metrics: {
          'Non-English Deferral Compliance': {
            score: 'Answered Anyway',
            reason: 'Answered the request in French.',
            backend: 'custom',
            description: '',
            is_successful: false,
          },
        },
      },
      status: { id: u(10), name: 'Pass' },
      last_review: { status: { id: u(10), name: 'Pass' } },
    } as unknown as Partial<TestResultDetail>);

    render(<TestDetailConversationTab test={test} />);

    expect(lastSummary[0].success).toBe(true);
  });
});
