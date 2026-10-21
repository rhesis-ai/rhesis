import React from 'react';
import { act, render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TestDetailConversationTab from '../TestDetailConversationTab';
import type {
  ConversationTurn,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

// ---- Stub children: capture what ConversationHistory and TraceDrawer get ----

let lastSummary: ConversationTurn[] = [];
let lastOnResponseClick: ((turnNumber: number) => void) | undefined;
let lastDrawerProps: {
  open?: boolean;
  traceId?: string | null;
  initialTurnIndex?: number;
} = {};

jest.mock('@/components/common/ConversationHistory', () => ({
  __esModule: true,
  default: ({
    conversationSummary,
    onResponseClick,
  }: {
    conversationSummary: ConversationTurn[];
    onResponseClick?: (turnNumber: number) => void;
  }) => {
    lastSummary = conversationSummary;
    lastOnResponseClick = onResponseClick;
    return null;
  },
}));

jest.mock('@/app/(protected)/traces/components/TraceDrawer', () => ({
  __esModule: true,
  default: (props: typeof lastDrawerProps) => {
    lastDrawerProps = props;
    return null;
  },
}));

let mockSessionStatus = 'unauthenticated';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: mockSessionStatus }),
}));

const mockListTraces = jest.fn();
const mockGetTrace = jest.fn();
const mockGetSpanFiles = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({
      listTraces: mockListTraces,
      getTrace: mockGetTrace,
    }),
    getFilesClient: () => ({ getSpanFiles: mockGetSpanFiles }),
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
    mockSessionStatus = 'unauthenticated';
    mockListTraces.mockResolvedValue({ traces: [] });
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

  it('follows a human annotation that overrides a failed result', () => {
    // The backend applies and persists a test-level annotation's verdict
    // synchronously (see services/annotation_override/), so an annotated
    // result's execution/verdict already reflect the override by the time
    // the client has it -- the raw is_successful=false metric stays as the
    // pre-annotation record.
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
      last_annotation: { status: { status_id: u(10), name: 'Pass' } },
    } as unknown as Partial<TestResultDetail>);

    render(<TestDetailConversationTab test={test} />);

    expect(lastSummary[0].success).toBe(true);
  });
});

// Three turns, each with a target reply.
const makeMultiTurnResult = (stored = true): TestResultDetail =>
  ({
    id: u(2),
    test_output: {
      goal: 'g',
      conversation_summary: stored
        ? [1, 2, 3].map(turn => ({
            turn,
            timestamp: '',
            session_id: '',
            penelope_reasoning: '',
            penelope_message: `question ${turn}`,
            target_response: `answer ${turn}`,
            success: true,
          }))
        : [],
      goal_evaluation: {},
    },
    status: { id: u(10), name: 'Pass' },
  }) as unknown as TestResultDetail;

// Deliberately out of order: the tab sorts by start time.
const trace = (id: string, minute: number) => ({
  trace_id: id,
  project_id: 'p',
  start_time: `2026-10-21T10:0${minute}:00Z`,
});

const rootSpan = (turn: number) => ({
  id: `span-${turn}`,
  span_id: `s${turn}`,
  start_time: '',
  status_code: 'OK',
  attributes: {
    'rhesis.conversation.input': `question ${turn}`,
    'rhesis.conversation.output': `answer ${turn}`,
  },
});

// One trace per turn: trace tN holds turn N's root span.
const oneTracePerTurn = () => {
  mockListTraces.mockResolvedValue({
    traces: [trace('t3', 3), trace('t1', 1), trace('t2', 2)],
  });
  mockGetTrace.mockImplementation(async (traceId: string) => ({
    root_spans: [rootSpan(Number(traceId.slice(1)))],
  }));
};

// One trace with a root span per turn.
const oneTraceForAllTurns = () => {
  mockListTraces.mockResolvedValue({ traces: [trace('t1', 1)] });
  mockGetTrace.mockResolvedValue({
    root_spans: [rootSpan(1), rootSpan(2), rootSpan(3)],
  });
};

describe('TestDetailConversationTab — traces with one trace per turn or one for all', () => {
  beforeEach(() => {
    lastSummary = [];
    lastOnResponseClick = undefined;
    lastDrawerProps = {};
    mockSessionStatus = 'authenticated';
    mockGetSpanFiles.mockImplementation(async (spanId: string) => [
      { id: `file-of-${spanId}` },
    ]);
  });

  const clickTurn = async (turnNumber: number) => {
    render(<TestDetailConversationTab test={makeMultiTurnResult()} />);
    await waitFor(() => expect(lastOnResponseClick).toBeDefined());
    act(() => lastOnResponseClick?.(turnNumber));
  };

  it('opens the clicked turn’s own trace when each turn is a trace', async () => {
    oneTracePerTurn();

    await clickTurn(2);

    expect(lastDrawerProps).toMatchObject({
      open: true,
      traceId: 't2',
      initialTurnIndex: 0,
    });
  });

  it('opens the turn’s root span when one trace holds every turn', async () => {
    oneTraceForAllTurns();

    await clickTurn(2);

    expect(lastDrawerProps).toMatchObject({
      open: true,
      traceId: 't1',
      initialTurnIndex: 1,
    });
  });

  it.each([
    ['each turn is a trace', oneTracePerTurn],
    ['one trace holds every turn', oneTraceForAllTurns],
  ])('attaches each turn’s own span files when %s', async (_, setup) => {
    setup();

    render(<TestDetailConversationTab test={makeMultiTurnResult()} />);

    await waitFor(() =>
      expect(lastSummary.map(t => t.penelope_files?.[0]?.id)).toEqual([
        'file-of-span-1',
        'file-of-span-2',
        'file-of-span-3',
      ])
    );
  });

  it('rebuilds every turn from spans when each turn is a trace', async () => {
    oneTracePerTurn();

    render(<TestDetailConversationTab test={makeMultiTurnResult(false)} />);

    await waitFor(() =>
      expect(lastSummary.map(t => t.target_response)).toEqual([
        'answer 1',
        'answer 2',
        'answer 3',
      ])
    );
  });
});
