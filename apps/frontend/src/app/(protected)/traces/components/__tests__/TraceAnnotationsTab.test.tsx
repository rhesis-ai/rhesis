import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import TraceAnnotationsTab from '../TraceAnnotationsTab';
import type {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u-1' } } }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('../TraceAnnotationDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

// Surfaces what the tab hands the shared panel.
jest.mock('@/components/annotations/AnnotationsPanel', () => ({
  __esModule: true,
  default: ({
    automatedStatus,
    hasConflict,
  }: {
    automatedStatus: { label: string; count?: string } | null;
    hasConflict?: boolean;
  }) => (
    <div>
      <span data-testid="automated">
        {automatedStatus
          ? `${automatedStatus.label} ${automatedStatus.count}`
          : 'none'}
      </span>
      <span data-testid="conflict">{String(!!hasConflict)}</span>
    </div>
  ),
}));

const passedAnnotation = {
  last_annotation: { status: { name: 'Pass' } },
  matches_annotation: false,
};

function renderTab(span: Partial<SpanNode>) {
  return render(
    <TraceAnnotationsTab
      selectedSpan={{ id: 's-1', ...span } as unknown as SpanNode}
      trace={{} as TraceDetailResponse}
      onTraceUpdated={jest.fn()}
    />
  );
}

describe('TraceAnnotationsTab', () => {
  it.each([
    ['no trace metrics', { trace_metrics: undefined }],
    [
      'empty metric sections',
      {
        trace_metrics: {
          turn_metrics: { metrics: {} },
          conversation_metrics: { metrics: {} },
        },
      },
    ],
  ])('shows no automated verdict and no conflict with %s', (_, metrics) => {
    renderTab({ ...metrics, ...passedAnnotation } as Partial<SpanNode>);

    expect(screen.getByTestId('automated')).toHaveTextContent('none');
    expect(screen.getByTestId('conflict')).toHaveTextContent('false');
  });

  it('still flags a human verdict that disagrees with the metrics', () => {
    renderTab({
      trace_metrics: {
        turn_metrics: { metrics: { Tone: { is_successful: false } } },
      },
      ...passedAnnotation,
    } as unknown as Partial<SpanNode>);

    expect(screen.getByTestId('automated')).toHaveTextContent('Failed 0/1');
    expect(screen.getByTestId('conflict')).toHaveTextContent('true');
  });
});
