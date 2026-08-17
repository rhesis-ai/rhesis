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

import { useUsage } from '@/contexts/UsageContext';

/** Build a `UsageResourceItem`; `ceiling` defaults to `limit` (a hard tier). */
function item(
  used: number,
  limit: number | null,
  ceiling?: number | null
): UsageResourceItem {
  return {
    used,
    limit,
    ceiling: ceiling === undefined ? limit : ceiling,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind: 'flow',
  };
}

function mockUsage(
  resources: Record<string, UsageResourceItem>,
  loading = false
) {
  (useUsage as jest.Mock).mockReturnValue({
    resources,
    edition: 'community',
    loading,
    error: null,
  });
}

afterEach(() => {
  jest.clearAllMocks();
});

describe('QuotaBanner', () => {
  it('renders nothing while usage is still loading', () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(999, 1000) }, true);
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

  it('warns once a resource crosses 80% utilization', () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    render(<QuotaBanner />);
    expect(screen.getByText(/80% of your test runs limit/i)).toBeInTheDocument();
  });

  it('treats a limit of zero as fully consumed rather than skipping it', () => {
    // `limit: 0` is a real configured value meaning "none allowed". Skipping
    // it hid the banner from exactly the orgs that were already blocked.
    mockUsage({ [QuotaResource.PROJECTS]: item(0, 0) });
    render(<QuotaBanner />);
    expect(screen.getByText(/100% of your projects limit/i)).toBeInTheDocument();
  });

  it('surfaces only the worst resource when several are over the threshold', () => {
    mockUsage({
      [QuotaResource.TEST_EXECUTIONS]: item(850, 1000),
      [QuotaResource.PROJECTS]: item(99, 100),
    });
    render(<QuotaBanner />);
    expect(screen.getByText(/99% of your projects limit/i)).toBeInTheDocument();
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

  it('stays dismissed for the resource that was dismissed', async () => {
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    render(<QuotaBanner />);

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    expect(screen.queryByText(/test runs limit/i)).not.toBeInTheDocument();
  });

  it('re-surfaces when a different resource crosses the threshold', async () => {
    const { rerender } = render(<QuotaBanner />);
    mockUsage({ [QuotaResource.TEST_EXECUTIONS]: item(800, 1000) });
    rerender(<QuotaBanner />);

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    // A dismissed test-runs warning must not silence a later seats warning.
    mockUsage({
      [QuotaResource.TEST_EXECUTIONS]: item(800, 1000),
      [QuotaResource.SEATS]: item(10, 10),
    });
    rerender(<QuotaBanner />);

    expect(screen.getByText(/100% of your seats limit/i)).toBeInTheDocument();
  });
});
