import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';
import TraceDrawer from '../TraceDrawer';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

const getTrace = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({ getTrace }),
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
  default: ({ span }: { span: SpanNode | null }) => (
    <div data-testid="span-details">{span?.span_id ?? 'none'}</div>
  ),
}));
jest.mock('../ConversationTraceView', () => ({
  __esModule: true,
  default: () => <div data-testid="conversation-view" />,
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

const scrollIntoView = jest.fn();

beforeAll(() => {
  Element.prototype.scrollIntoView = scrollIntoView;
});

beforeEach(() => {
  getTrace.mockReset();
  scrollIntoView.mockClear();
  getTrace.mockResolvedValue(conversationTrace());
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
