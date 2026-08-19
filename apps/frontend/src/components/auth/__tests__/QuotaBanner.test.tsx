import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import QuotaBanner from '../QuotaBanner';
import { QuotaResource } from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

jest.mock('@/contexts/UsageContext', () => ({
  useUsage: jest.fn(),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

import { useUsage } from '@/contexts/UsageContext';

/** Build a `UsageResourceItem`; `ceiling` defaults to `limit` (a hard tier). */
function item(
  used: number,
  limit: number | null,
  options: { kind?: 'flow' | 'stock'; ceiling?: number | null } = {}
): UsageResourceItem {
  const { kind = 'flow', ceiling } = options;
  return {
    used,
    limit,
    ceiling: ceiling === undefined ? limit : ceiling,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind,
  };
}

function mockUsage(
  resources: Record<string, UsageResourceItem>,
  options: { loading?: boolean; edition?: string | null } = {}
) {
  const { loading = false, edition = 'community' } = options;
  (useUsage as jest.Mock).mockReturnValue({
    resources,
    edition,
    loading,
    error: null,
  });
}

afterEach(() => {
  jest.clearAllMocks();
});

describe('QuotaBanner', () => {
  it('renders nothing while usage is still loading', () => {
    mockUsage(
      { [QuotaResource.TEST_EXECUTIONS]: item(999, 1000) },
      { loading: true }
    );
    const { container } = render(<QuotaBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when every resource is comfortably under the threshold', () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(10, 1000) });
    const { container } = render(<QuotaBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for an unlimited resource no matter how high usage is', () => {
    mockUsage({ [QuotaResource.MODEL_TOKENS]: item(10_000_000, null) });
    const { container } = render(<QuotaBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('names the organization, not the reader, once a flow resource crosses 80%', () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    render(<QuotaBanner />);
    expect(
      screen.getByText(
        /Your organization has used 80% of its test runs for this period\./i
      )
    ).toBeInTheDocument();
  });

  it('counts rather than percentages a stock resource approaching its limit', () => {
    mockUsage({
      [QuotaResource.PROJECTS]: item(4, 5, { kind: 'stock', ceiling: 5 }),
    });
    render(<QuotaBanner />);
    expect(
      screen.getByText(/Your organization is using 4 of 5 projects\./i)
    ).toBeInTheDocument();
  });

  it('treats a limit of zero as blocked rather than skipping it', () => {
    // `limit: 0` is a real configured value meaning "none allowed", and with
    // no grace band `used (0) >= ceiling (0)` immediately -- blocked, not
    // merely "approaching". Skipping it hid the banner from exactly the
    // orgs that were already blocked.
    mockUsage({
      [QuotaResource.PROJECTS]: item(0, 0, { kind: 'stock' }),
    });
    render(<QuotaBanner />);
    expect(
      screen.getByText(
        /Your organization is at its projects limit \(0 of 0\)\./i
      )
    ).toBeInTheDocument();
  });

  it('surfaces only the worst resource when several are over the threshold', () => {
    mockUsage({
      [QuotaResource.TEST_EXECUTIONS]: item(850, 1000),
      [QuotaResource.PROJECTS]: item(99, 100, { kind: 'stock' }),
    });
    render(<QuotaBanner />);
    expect(screen.getByText(/99 of 100 projects/i)).toBeInTheDocument();
    expect(screen.queryByText(/test runs/i)).not.toBeInTheDocument();
  });

  it('ignores a resource the label map does not know about', () => {
    // The backend can add a QuotaResource before constants/quota.ts catches
    // up. This component renders inside the protected layout, so throwing on
    // a missing label would take down every page, not just the banner.
    mockUsage({ some_future_resource: item(99, 100) });
    const { container } = render(<QuotaBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('offers to upgrade on a community-edition org', () => {
    mockUsage(
      { [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) },
      { edition: 'community' }
    );
    render(<QuotaBanner />);
    expect(
      screen.getByRole('link', { name: /upgrade plan/i })
    ).toBeInTheDocument();
  });

  it('does not offer to upgrade a paying org', () => {
    mockUsage(
      { [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) },
      { edition: 'pro' }
    );
    render(<QuotaBanner />);
    expect(
      screen.queryByRole('link', { name: /upgrade plan/i })
    ).not.toBeInTheDocument();
  });

  it('stays dismissed for the resource that was dismissed', async () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    render(<QuotaBanner />);

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    expect(screen.queryByText(/test runs/i)).not.toBeInTheDocument();
  });

  it('re-surfaces when a different resource crosses the threshold', async () => {
    const { rerender } = render(<QuotaBanner />);
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    rerender(<QuotaBanner />);

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    // A dismissed test-runs warning must not silence a later seats warning.
    mockUsage({
      [QuotaResource.TEST_EXECUTIONS]: item(800, 1000),
      [QuotaResource.SEATS]: item(10, 10, { kind: 'stock' }),
    });
    rerender(<QuotaBanner />);

    expect(
      screen.getByText(
        /Your organization is at its seats limit \(10 of 10\)\./i
      )
    ).toBeInTheDocument();
  });
});
