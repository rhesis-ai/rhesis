import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import TraceAnnotationDrawer from '../TraceAnnotationDrawer';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

jest.mock('@/components/common/StatusChip', () => ({
  __esModule: true,
  default: ({ label }: { label: string }) => (
    <span data-testid="status-chip">{label}</span>
  ),
}));

// Renders the trace-specific context block for a whole-trace target.
jest.mock('@/components/annotations/AnnotationDrawer', () => ({
  __esModule: true,
  default: ({
    renderContext,
  }: {
    renderContext: (target: { type: string }) => React.ReactNode;
  }) => <div>{renderContext({ type: 'trace' })}</div>,
}));

function renderDrawer(span: Partial<SpanNode>) {
  return render(
    <TraceAnnotationDrawer
      open
      onClose={jest.fn()}
      selectedSpan={{ id: 's-1', ...span } as unknown as SpanNode}
      onSave={jest.fn()}
    />
  );
}

describe('TraceAnnotationDrawer', () => {
  it('says the trace is not evaluated instead of showing Failed when no metric ran', () => {
    renderDrawer({ trace_metrics: undefined });

    expect(
      screen.getByText('Not evaluated. No metrics ran on this trace.')
    ).toBeInTheDocument();
    expect(screen.queryByTestId('status-chip')).not.toBeInTheDocument();
  });

  it('shows the metric count when metrics ran', () => {
    renderDrawer({
      execution: 'ok',
      verdict: 'pass',
      trace_metrics: {
        turn_metrics: { metrics: { Tone: { is_successful: true } } },
      },
    } as unknown as Partial<SpanNode>);

    expect(screen.getByTestId('status-chip')).toHaveTextContent('Passed');
    expect(screen.getByText('1/1 metrics passed')).toBeInTheDocument();
  });
});
