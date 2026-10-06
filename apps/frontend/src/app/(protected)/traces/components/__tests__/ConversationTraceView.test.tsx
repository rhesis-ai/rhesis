import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ConversationTraceView from '../ConversationTraceView';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

const mockUseCan = jest.fn(() => true);

jest.mock('@/components/common/Can', () => ({
  useCan: () => mockUseCan(),
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({})),
}));

// Stand-in that exposes the per-turn hook as a plain button.
jest.mock('@/components/common/ConversationHistory', () => ({
  __esModule: true,
  default: ({
    onCreateTestFromTurn,
  }: {
    onCreateTestFromTurn?: (turnNumber: number) => void;
  }) =>
    onCreateTestFromTurn ? (
      <button onClick={() => onCreateTestFromTurn(2)}>turn-2-test</button>
    ) : null,
}));

jest.mock('@/components/tests/CreateTestFromConversationDrawer', () => ({
  __esModule: true,
  default: ({
    testType,
    messages,
    endpointId,
  }: {
    testType: string;
    messages: Array<{ role: string; content: string }>;
    endpointId?: string;
  }) => (
    <div data-testid="test-drawer">
      <span data-testid="test-type">{testType}</span>
      <span data-testid="endpoint">{endpointId}</span>
      <span data-testid="messages">
        {messages.map(m => `${m.role}:${m.content}`).join('|')}
      </span>
    </div>
  ),
}));

const span = (input: string, output: string): SpanNode =>
  ({
    span_id: input,
    start_time: '2026-10-05T10:00:00Z',
    status_code: 'OK',
    attributes: {
      'rhesis.conversation.input': input,
      'rhesis.conversation.output': output,
    },
  }) as unknown as SpanNode;

const rootSpans = [
  span('Berlin to Paris?', 'Try Air France.'),
  span('And to New York?', 'Corvane Airways.'),
];

const trace = {
  trace_id: 't-1',
  conversation_id: 'c-1',
  endpoint: { id: 'endpoint-1', name: 'travel_agent_chat' },
  root_spans: rootSpans,
} as unknown as TraceDetailResponse;

function renderView() {
  return render(<ConversationTraceView trace={trace} rootSpans={rootSpans} />);
}

describe('ConversationTraceView create test', () => {
  beforeEach(() => mockUseCan.mockReturnValue(true));

  it('opens a multi-turn draft with the whole conversation', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(
      await screen.findByRole('button', {
        name: 'Create multi-turn test from conversation',
      })
    );

    expect(screen.getByTestId('test-type')).toHaveTextContent('Multi-Turn');
    expect(screen.getByTestId('endpoint')).toHaveTextContent('endpoint-1');
    expect(screen.getByTestId('messages')).toHaveTextContent(
      'user:Berlin to Paris?|assistant:Try Air France.|user:And to New York?|assistant:Corvane Airways.'
    );
  });

  it('opens a single-turn draft with only the clicked turn', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(
      await screen.findByRole('button', { name: 'turn-2-test' })
    );

    expect(screen.getByTestId('test-type')).toHaveTextContent('Single-Turn');
    expect(screen.getByTestId('messages')).toHaveTextContent(
      'user:And to New York?|assistant:Corvane Airways.'
    );
  });

  it('hides both buttons from users who cannot create tests', async () => {
    mockUseCan.mockReturnValue(false);
    renderView();

    await waitFor(() =>
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    );
    expect(
      screen.queryByRole('button', {
        name: 'Create multi-turn test from conversation',
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'turn-2-test' })
    ).not.toBeInTheDocument();
  });
});
