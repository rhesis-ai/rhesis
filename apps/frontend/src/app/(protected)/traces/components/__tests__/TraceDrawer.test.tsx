import React from 'react';
import { render, screen, waitFor, within } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TraceDrawer from '../TraceDrawer';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

const getTrace = jest.fn();
const listTraces = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({ getTrace, listTraces }),
  })),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'authenticated' }),
}));

jest.mock('@/contexts/CurrencyContext', () => ({
  useCurrency: () => ({ format: (v: number) => `$${v}` }),
}));

jest.mock('@/components/annotations/useAnnotationTargets', () => ({
  useTraceAnnotationTargets: () => ({ metrics: [], turns: [] }),
}));

// The details panel is large and fetches on its own; the drawer only hands it
// the selected span, which is all these tests look at.
jest.mock('../SpanDetailsPanel', () => ({
  __esModule: true,
  default: ({
    span,
    onTraceUpdated,
  }: {
    span: SpanNode | null;
    onTraceUpdated?: () => void;
  }) => (
    <>
      <div data-testid="span-details">{span?.span_id ?? 'none'}</div>
      <button onClick={onTraceUpdated}>refresh-trace</button>
    </>
  ),
}));
jest.mock('../ConversationTraceView', () => ({
  __esModule: true,
  default: ({
    rootSpans,
    onTurnClick,
  }: {
    rootSpans?: SpanNode[];
    onTurnClick?: (turnNumber: number) => void;
  }) => (
    <div data-testid="conversation-view">
      <span data-testid="conversation-roots">
        {rootSpans?.map(s => s.span_name).join(',')}
      </span>
      {onTurnClick && (
        <button onClick={() => onTurnClick(3)}>open-turn-3</button>
      )}
    </div>
  ),
}));
jest.mock('../SpanSequenceView', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('../SpanGraphView', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('../TraceAnnotationDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

function span(
  span_id: string,
  span_name: string,
  children: SpanNode[] = []
): SpanNode {
  return {
    span_id,
    span_name,
    span_kind: 'INTERNAL',
    start_time: '2026-01-01T00:00:00Z',
    end_time: '2026-01-01T00:00:01Z',
    duration_ms: 1000,
    status_code: 'OK',
    attributes: {},
    events: [],
    children,
  } as unknown as SpanNode;
}

function conversationTrace(): TraceDetailResponse {
  return {
    trace_id: 'trace-1',
    environment: 'development',
    conversation_id: 'conv-1',
    duration_ms: 2000,
    span_count: 5,
    error_count: 0,
    total_tokens: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_cost_usd: null,
    root_spans: [
      span('turn-1', 'turn.one', [span('t1-llm', 'ai.llm.invoke')]),
      span('turn-2', 'turn.two', [
        span('t2-agent', 'ai.agent.invoke', [
          span('t2-tool', 'ai.tool.invoke'),
        ]),
      ]),
    ],
  } as unknown as TraceDetailResponse;
}

// jsdom has no scrollIntoView; stub it and restore the original afterwards.
const scrollIntoView = jest.fn();
const originalScrollIntoView = Element.prototype.scrollIntoView;

beforeAll(() => {
  Element.prototype.scrollIntoView = scrollIntoView;
});

afterAll(() => {
  Element.prototype.scrollIntoView = originalScrollIntoView;
});

beforeEach(() => {
  getTrace.mockReset();
  listTraces.mockReset();
  scrollIntoView.mockClear();
  getTrace.mockResolvedValue(conversationTrace());
  listTraces.mockResolvedValue({ traces: [] });
});

function renderDrawer(
  props: Partial<React.ComponentProps<typeof TraceDrawer>> = {}
) {
  return render(
    <TraceDrawer
      open
      onClose={jest.fn()}
      traceId="trace-1"
      projectId="project-1"
      {...props}
    />
  );
}

async function selectedDetails() {
  return (await screen.findByTestId('span-details')).textContent;
}

function selectedTab() {
  return screen
    .getAllByRole('tab')
    .find(tab => tab.getAttribute('aria-selected') === 'true')?.textContent;
}

describe('TraceDrawer initial selection', () => {
  it('opens on the Tree tab with a nested span selected and scrolled to', async () => {
    renderDrawer({ initialSpanId: 't2-tool' });

    expect(await selectedDetails()).toBe('t2-tool');
    expect(selectedTab()).toBe('Tree');

    // Its ancestors are expanded, so the row itself is on screen.
    const row = document.querySelector('[data-span-id="t2-tool"]');
    expect(row).toHaveAttribute('data-selected', 'true');
    expect(screen.getByText('ai.agent.invoke')).toBeInTheDocument();
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
    );
    expect(scrollIntoView.mock.contexts).toContain(row);
  });

  it('prefers the span over the turn index', async () => {
    renderDrawer({ initialSpanId: 't2-agent', initialTurnIndex: 0 });

    expect(await selectedDetails()).toBe('t2-agent');
    expect(selectedTab()).toBe('Tree');
  });

  it('falls back to the first root when the span is not found', async () => {
    renderDrawer({ initialSpanId: 'missing' });

    expect(await selectedDetails()).toBe('turn-1');
    expect(selectedTab()).toBe('Conversation');
  });

  it('falls back to the turn index when the span is not found', async () => {
    renderDrawer({ initialSpanId: 'missing', initialTurnIndex: 1 });

    expect(await selectedDetails()).toBe('turn-2');
    expect(selectedTab()).toBe('Tree');
  });

  it('selects the first root without any initial target', async () => {
    renderDrawer();

    expect(await selectedDetails()).toBe('turn-1');
    expect(selectedTab()).toBe('Conversation');
  });

  it('opens the Tree tab first for a trace without a conversation', async () => {
    getTrace.mockResolvedValue({
      ...conversationTrace(),
      conversation_id: undefined,
    });
    renderDrawer({ initialSpanId: 't1-llm' });

    expect(await selectedDetails()).toBe('t1-llm');
    expect(selectedTab()).toBe('Tree');
  });
});

function summary(trace_id: string, second: number) {
  return {
    trace_id,
    project_id: 'project-1',
    start_time: `2026-01-01T00:00:0${second}Z`,
  };
}

// One trace per turn: tN holds turn N. Turn 1 was stored before the backend
// linked conversations, so it has no conversation_id of its own.
function oneTracePerTurn() {
  listTraces.mockResolvedValue({
    traces: [summary('t3', 3), summary('t1', 1), summary('t2', 2)],
  });
  getTrace.mockImplementation(async (traceId: string) => ({
    ...conversationTrace(),
    trace_id: traceId,
    conversation_id: traceId === 't1' ? undefined : 'conv-1',
    test_result: { id: 'result-1' },
    root_spans: [span(`${traceId}-root`, `turn.${traceId}`)],
  }));
}

function turnLabel() {
  return within(
    screen.getByRole('group', { name: 'Conversation turns' })
  ).getByText(/^Turn/).textContent;
}

describe('TraceDrawer turn navigation', () => {
  it('moves between root spans when one trace holds every turn', async () => {
    const user = userEvent.setup();
    listTraces.mockResolvedValue({ traces: [summary('trace-1', 1)] });
    renderDrawer();

    await screen.findByRole('group', { name: 'Conversation turns' });
    expect(turnLabel()).toBe('Turn 1 of 2');
    expect(
      screen.getByRole('button', { name: 'Previous turn' })
    ).toBeDisabled();
    expect(listTraces).toHaveBeenCalledWith({
      conversation_id: 'conv-1',
      project_id: undefined,
      limit: 100,
    });

    await user.click(screen.getByRole('button', { name: 'Next turn' }));

    expect(await selectedDetails()).toBe('turn-2');
    expect(turnLabel()).toBe('Turn 2 of 2');
    expect(screen.getByRole('button', { name: 'Next turn' })).toBeDisabled();
    // The loaded trace is reused, not fetched a second time.
    expect(getTrace).toHaveBeenCalledTimes(1);
  });

  it('loads the next or previous turn’s own trace when each turn is a trace', async () => {
    const user = userEvent.setup();
    oneTracePerTurn();
    renderDrawer({ traceId: 't2' });

    await screen.findByRole('group', { name: 'Conversation turns' });
    expect(turnLabel()).toBe('Turn 2 of 3');
    expect(listTraces).toHaveBeenCalledWith({
      test_result_id: 'result-1',
      limit: 100,
    });

    await user.click(screen.getByRole('button', { name: 'Next turn' }));
    await waitFor(() => expect(turnLabel()).toBe('Turn 3 of 3'));
    expect(await selectedDetails()).toBe('t3-root');
    expect(screen.getByRole('button', { name: 'Next turn' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Previous turn' }));
    await waitFor(() => expect(turnLabel()).toBe('Turn 2 of 3'));
    await user.click(screen.getByRole('button', { name: 'Previous turn' }));

    // Turn 1 has no conversation_id, and the switcher still knows the conversation.
    await waitFor(() => expect(turnLabel()).toBe('Turn 1 of 3'));
    expect(await selectedDetails()).toBe('t1-root');
    expect(
      screen.getByRole('button', { name: 'Previous turn' })
    ).toBeDisabled();
    expect(listTraces).toHaveBeenCalledTimes(1);
  });

  it('opens a turn clicked in the Conversation tab', async () => {
    const user = userEvent.setup();
    oneTracePerTurn();
    renderDrawer({ traceId: 't2' });

    await user.click(
      await screen.findByRole('button', { name: 'open-turn-3' })
    );

    await waitFor(() => expect(turnLabel()).toBe('Turn 3 of 3'));
    expect(await selectedDetails()).toBe('t3-root');
    expect(selectedTab()).toBe('Conversation');
  });

  it('shows no switcher for a conversation of one turn', async () => {
    listTraces.mockResolvedValue({ traces: [summary('trace-1', 1)] });
    getTrace.mockResolvedValue({
      ...conversationTrace(),
      root_spans: [span('turn-1', 'turn.one')],
    });
    renderDrawer();

    expect(await selectedDetails()).toBe('turn-1');
    await waitFor(() => expect(listTraces).toHaveBeenCalled());
    expect(
      screen.queryByRole('group', { name: 'Conversation turns' })
    ).not.toBeInTheDocument();
  });

  it('shows the loaded trace’s refreshed spans in the Conversation tab', async () => {
    const user = userEvent.setup();
    listTraces.mockResolvedValue({ traces: [summary('trace-1', 1)] });
    renderDrawer();
    await screen.findByRole('group', { name: 'Conversation turns' });

    const refreshed = conversationTrace();
    refreshed.root_spans[0] = span('turn-1', 'turn.one.annotated');
    getTrace.mockResolvedValue(refreshed);
    await user.click(screen.getByRole('button', { name: 'refresh-trace' }));

    await waitFor(() =>
      expect(screen.getByTestId('conversation-roots')).toHaveTextContent(
        'turn.one.annotated,turn.two'
      )
    );
  });
});
