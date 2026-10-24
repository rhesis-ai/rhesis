import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import EvaluationVerdict, { AGREE_COMMENT } from '../EvaluationVerdict';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const create = jest.fn();
jest.mock('@/hooks/useAnnotations', () => ({
  useAnnotationMutations: () => ({ create }),
}));

const getStatuses = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getStatusClient: () => ({ getStatuses }),
  })),
}));

const failingSpan = {
  id: 's-1',
  trace_metrics: {
    turn_metrics: {
      metrics: {
        Empathy: { is_successful: true },
        'Urgent care escalation': { is_successful: false },
      },
    },
  },
} as unknown as SpanNode;

beforeEach(() => {
  create.mockReset().mockResolvedValue({});
  getStatuses.mockReset().mockResolvedValue([
    { id: 'pass-id', name: 'Pass' },
    { id: 'fail-id', name: 'Fail' },
  ]);
});

describe('EvaluationVerdict', () => {
  it('shows the automated result next to an empty human one', () => {
    render(<EvaluationVerdict span={failingSpan} onChanged={jest.fn()} />);

    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('1/2 metrics passed')).toBeInTheDocument();
    expect(screen.getByText('Not annotated')).toBeInTheDocument();
  });

  it('records agreement as an annotation with the automated status', async () => {
    const user = userEvent.setup();
    render(<EvaluationVerdict span={failingSpan} onChanged={jest.fn()} />);

    await user.click(screen.getByRole('button', { name: /agree/i }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        statusId: 'fail-id',
        comments: AGREE_COMMENT,
      })
    );
  });

  it('offers no Agree once a human verdict exists', () => {
    render(
      <EvaluationVerdict
        span={
          {
            ...failingSpan,
            last_annotation: {
              target_type: 'trace',
              status: { name: 'Fail' },
              user: { name: 'Sam' },
            },
          } as unknown as SpanNode
        }
        onChanged={jest.fn()}
      />
    );

    expect(screen.queryByRole('button', { name: /agree/i })).toBeNull();
    expect(screen.getByText(/by Sam/)).toBeInTheDocument();
  });

  it('offers no Agree when nothing automated ran', () => {
    render(
      <EvaluationVerdict
        span={{ id: 's-2' } as unknown as SpanNode}
        onChanged={jest.fn()}
      />
    );

    expect(screen.getByText('Not evaluated')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /agree/i })).toBeNull();
  });
});
