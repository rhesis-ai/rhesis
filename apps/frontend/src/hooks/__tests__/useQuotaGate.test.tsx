import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import {
  useQuotaErrorHandler,
  useQuotaGate,
  useQuotaMessageFor,
} from '@/hooks/useQuotaGate';
import { QuotaResource } from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

jest.mock('@/contexts/UsageContext', () => ({
  useResourceUsage: jest.fn(),
  useUsage: jest.fn(() => ({
    resources: {},
    edition: 'community',
    loading: false,
    error: null,
  })),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: jest.fn(() => true),
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

import { useResourceUsage, useUsage } from '@/contexts/UsageContext';
import { useCan } from '@/components/common/Can';

function usage(
  used: number,
  limit: number | null,
  ceiling: number | null
): UsageResourceItem {
  return {
    used,
    limit,
    ceiling,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow',
  };
}

function mockUsage(item: UsageResourceItem | null) {
  (useResourceUsage as jest.Mock).mockReturnValue(item);
}

/** Renders a hook's output as text so we can assert on it without extra deps. */
function GateProbe({ amount }: { amount?: number }) {
  const gate = useQuotaGate(QuotaResource.TEST_EXECUTIONS, amount);
  return (
    <div>
      <span data-testid="exhausted">{String(gate.exhausted)}</span>
      <span data-testid="message">{gate.message ?? ''}</span>
      <span data-testid="notice">{gate.notice ? 'has-notice' : ''}</span>
    </div>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  (useCan as jest.Mock).mockReturnValue(true);
  (useUsage as jest.Mock).mockReturnValue({
    resources: {},
    edition: 'community',
    loading: false,
    error: null,
  });
});

describe('useQuotaGate', () => {
  it('allows an action well under the ceiling', () => {
    mockUsage(usage(10, 100, 100));
    render(<GateProbe />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('false');
    expect(screen.getByTestId('notice')).toBeEmptyDOMElement();
  });

  it('fails open while usage is still loading', () => {
    // Blocking on unknown usage would disable the action for everyone during
    // the first round trip; the server-side 402 is the real gate.
    mockUsage(null);
    render(<GateProbe />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('false');
  });

  it('never blocks an unlimited resource', () => {
    mockUsage(usage(10_000_000, null, null));
    render(<GateProbe />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('false');
  });

  it('allows the soft-tier grace band rather than stopping at the limit', () => {
    // limit 100, ceiling 125: gating on `limit` would erase the whole band.
    mockUsage(usage(110, 100, 125));
    render(<GateProbe />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('false');
  });

  it('blocks at the ceiling and offers copy', () => {
    mockUsage(usage(125, 100, 125));
    render(<GateProbe />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('true');
    expect(screen.getByTestId('notice')).toHaveTextContent('has-notice');
    expect(screen.getByTestId('message')).toHaveTextContent(
      /Your organization is at its test runs limit/
    );
  });

  it('accounts for an action that consumes several units at once', () => {
    // Two slots left, but this submit wants five.
    mockUsage(usage(98, 100, 100));
    render(<GateProbe amount={5} />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('true');
  });

  it('lets a multi-unit action through when it still fits exactly', () => {
    mockUsage(usage(98, 100, 100));
    render(<GateProbe amount={2} />);
    expect(screen.getByTestId('exhausted')).toHaveTextContent('false');
  });

  it('points a member at an admin rather than at the upgrade link', () => {
    (useCan as jest.Mock).mockReturnValue(false);
    mockUsage(usage(100, 100, 100));
    render(<GateProbe />);
    expect(screen.getByTestId('message')).toHaveTextContent(
      /Ask an org admin to raise this limit/
    );
  });
});

function MessageForProbe({ amount }: { amount: number }) {
  const messageFor = useQuotaMessageFor(QuotaResource.SEATS);
  return <span data-testid="msg">{messageFor(amount) ?? 'allowed'}</span>;
}

describe('useQuotaMessageFor', () => {
  it('decides against the amount handed in at call time', () => {
    mockUsage(usage(8, 10, 10));
    const { rerender } = render(<MessageForProbe amount={2} />);
    expect(screen.getByTestId('msg')).toHaveTextContent('allowed');

    rerender(<MessageForProbe amount={3} />);
    expect(screen.getByTestId('msg')).toHaveTextContent(
      /Your organization is at its seats limit/
    );
  });
});

function ErrorProbe({ err }: { err: unknown }) {
  const asQuotaError = useQuotaErrorHandler();
  const result = asQuotaError(err);
  return <span data-testid="out">{result ? result.message : 'not-quota'}</span>;
}

describe('useQuotaErrorHandler', () => {
  function quota402(data: Record<string, unknown>) {
    const err = new Error('API error: 402') as Error & {
      status?: number;
      data?: Record<string, unknown>;
    };
    err.status = 402;
    err.data = data;
    return err;
  }

  it('turns a quota 402 into copy', () => {
    mockUsage(null);
    render(
      <ErrorProbe
        err={quota402({
          error: 'quota_exceeded',
          resource: 'projects',
          used: 1,
          limit: 1,
          kind: 'stock',
        })}
      />
    );
    expect(screen.getByTestId('out')).toHaveTextContent(
      /Your organization is at its projects limit \(1 of 1\)\. Delete a project/
    );
  });

  it('passes through anything that is not a quota error', () => {
    mockUsage(null);
    const other = new Error('boom') as Error & { status?: number };
    other.status = 500;
    render(<ErrorProbe err={other} />);
    expect(screen.getByTestId('out')).toHaveTextContent('not-quota');
  });

  it('ignores a resource the frontend does not know yet', () => {
    mockUsage(null);
    render(
      <ErrorProbe
        err={quota402({
          error: 'quota_exceeded',
          resource: 'some_future_resource',
          used: 1,
          limit: 1,
        })}
      />
    );
    expect(screen.getByTestId('out')).toHaveTextContent('not-quota');
  });
});
