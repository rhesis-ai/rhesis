import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import RunDrawer from '../RunDrawer';
import type { BaseDrawerProps } from '../BaseDrawer';
import { QuotaResource } from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

/**
 * Covers only the quota-gate logic RunDrawer added on top of its existing
 * (untested) execute-configuration form: `canExecute` blocking on the
 * resource's `ceiling`, not its `limit`. `rerunTestRun` mode is used because
 * it takes `endpointId`/`testSetId` directly as props (`RerunConfig`) rather
 * than through dropdown selection, and its config renders read-only fields
 * instead of the editable project/endpoint pickers -- the minimal surface
 * that reaches `canExecute` without exercising the rest of this 2000+ line
 * form, which has no existing test coverage of its own.
 */

jest.mock('../BaseDrawer', () => ({
  __esModule: true,
  default: ({
    open,
    children,
    onSave,
    saveButtonText,
    saveDisabled,
    error,
    title,
  }: BaseDrawerProps) =>
    open ? (
      <div data-testid="base-drawer">
        <h2>{title}</h2>
        {error && <div role="alert">{error}</div>}
        {children}
        <button onClick={onSave} disabled={saveDisabled}>
          {saveButtonText}
        </button>
      </div>
    ) : null,
}));

jest.mock('../ModelSelector', () => ({
  __esModule: true,
  default: () => <div data-testid="model-selector-stub" />,
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoints: jest.fn(() => ({ data: [], isLoading: false })),
}));

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({ status: 'authenticated' })),
}));

jest.mock('../NotificationContext', () => ({
  useNotifications: jest.fn(() => ({ show: jest.fn(), close: jest.fn() })),
}));

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
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestSetsClient: () => ({
      getTestSet: jest
        .fn()
        .mockResolvedValue({ test_set_type: { type_value: 'single_turn' } }),
      getTestSetMetrics: jest.fn().mockResolvedValue([]),
    }),
    getParametersClient: () => ({
      getExperiment: jest.fn().mockResolvedValue(null),
    }),
    getProjectsClient: () => ({
      getProjects: jest.fn().mockResolvedValue({ data: [] }),
    }),
    getTestRunsClient: () => ({}),
  })),
}));

import { useResourceUsage } from '@/contexts/UsageContext';

/** `ceiling` defaults to `limit` (a hard-tier verdict, no grace band). */
function usageItem(
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

function mockExecutionUsage(item: UsageResourceItem | null) {
  (useResourceUsage as jest.Mock).mockImplementation((resource: string) =>
    resource === QuotaResource.TEST_EXECUTIONS ? item : null
  );
}

const rerunConfig = {
  testSetId: 'ts-1',
  testSetName: 'My Test Set',
  endpointId: 'ep-1',
  endpointName: 'My Endpoint',
  projectName: 'My Project',
  testRunId: 'run-1',
};

function renderRunDrawer() {
  return render(
    <RunDrawer
      open
      onClose={jest.fn()}
      onSuccess={jest.fn()}
      mode="rerunTestRun"
      data={rerunConfig}
    />
  );
}

describe('RunDrawer quota gate', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('enables Run when usage has not reached the limit', () => {
    mockExecutionUsage(usageItem(50, 100));
    renderRunDrawer();

    expect(screen.getByRole('button', { name: /re-run tests/i })).toBeEnabled();
  });

  it('disables Run at the ceiling, not the bare limit', () => {
    // Soft tier: limit 100, 25% tolerance -> ceiling 125. Past the
    // advertised limit but still inside the grace band the backend allows.
    mockExecutionUsage(usageItem(110, 100, 125));
    renderRunDrawer();

    expect(screen.getByRole('button', { name: /re-run tests/i })).toBeEnabled();
  });

  it('disables Run once usage reaches the ceiling', () => {
    mockExecutionUsage(usageItem(125, 100, 125));
    renderRunDrawer();

    expect(
      screen.getByRole('button', { name: /re-run tests/i })
    ).toBeDisabled();
  });

  it('never blocks an unlimited resource', () => {
    mockExecutionUsage(usageItem(1_000_000, null, null));
    renderRunDrawer();

    expect(screen.getByRole('button', { name: /re-run tests/i })).toBeEnabled();
  });

  it('does not block while usage is still loading (useResourceUsage returns null)', () => {
    mockExecutionUsage(null);
    renderRunDrawer();

    expect(screen.getByRole('button', { name: /re-run tests/i })).toBeEnabled();
  });

  it('shows the quota-exhausted message in the drawer error slot once blocked', () => {
    mockExecutionUsage(usageItem(100, 100, 100));
    renderRunDrawer();

    expect(screen.getByRole('alert')).toHaveTextContent(/test runs limit/i);
  });
});
