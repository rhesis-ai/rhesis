import React from 'react';
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@testing-library/jest-dom';
import RunDrawer from '../RunDrawer';
import type { BaseDrawerProps } from '../BaseDrawer';
import { QuotaResource } from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

/**
 * The quota gate (`canExecute` blocking on the resource's `ceiling`, not its
 * `limit`) uses `rerunTestRun` mode, which takes `endpointId`/`testSetId` as
 * props instead of through dropdowns. The section tests use `executeTestSet`,
 * the mode with every section, including "When".
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
    footerSummary,
  }: BaseDrawerProps) =>
    open ? (
      <div data-testid="base-drawer">
        <h2>{title}</h2>
        {error && <div role="alert">{error}</div>}
        {children}
        <p data-testid="footer-summary">{footerSummary}</p>
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

// One array for every render, as React Query gives: a fresh one each call
// re-runs the drawer's endpoint filter forever.
const mockEndpointsResult = { data: [], isLoading: false };
jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoints: jest.fn(() => mockEndpointsResult),
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

/** Tests in the drawer's test set; the gate asks for this many. */
let mockTestSetTestCount = 1;
const mockGetTestSetTests = jest.fn(() =>
  Promise.resolve({
    data: [],
    pagination: { totalCount: mockTestSetTestCount },
  })
);

/** The tags on the drawer's test set's tests. */
let mockTestSetTestTags: { name: string; test_count: number }[] = [];
const mockGetTestSetTestTags = jest.fn((_id: string) =>
  Promise.resolve(mockTestSetTestTags)
);

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestSetsClient: () => ({
      getTestSetTests: mockGetTestSetTests,
      getTestSetTestTags: mockGetTestSetTestTags,
      getTestSet: jest.fn().mockResolvedValue({
        name: 'Safety checks',
        test_set_type: { type_value: 'single_turn' },
      }),
      getTestSetMetrics: jest.fn().mockResolvedValue([]),
      getLastTestRun: jest.fn().mockResolvedValue(null),
      getTestSets: jest.fn((params: { $filter?: string }) =>
        Promise.resolve({
          data: params?.$filter
            ? [
                { id: 'ts-a', name: 'Billing' },
                { id: 'ts-b', name: 'Claims' },
              ]
            : [],
          pagination: { totalCount: 0 },
        })
      ),
    }),
    getTestRunSchedulesClient: () => ({
      preview: jest.fn().mockResolvedValue({ repeats: 'Every day', next: [] }),
    }),
    getParametersClient: () => ({
      getExperiment: jest.fn().mockResolvedValue(null),
    }),
    getProjectsClient: () => ({
      getProjects: jest.fn().mockResolvedValue({ data: [] }),
    }),
    getTestRunsClient: () => ({}),
    getTagsClient: () => ({
      getTags: jest.fn().mockResolvedValue([{ id: 'tag-1', name: 'nightly' }]),
    }),
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
    mockTestSetTestCount = 1;
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

    expect(screen.getByRole('alert')).toHaveTextContent(
      /test executions limit/i
    );
  });

  it("disables Run when the run's tests don't fit in what's left", async () => {
    mockTestSetTestCount = 20;
    mockExecutionUsage(usageItem(90, 100));
    renderRunDrawer();

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /re-run tests/i })
      ).toBeDisabled()
    );
    expect(mockGetTestSetTests).toHaveBeenCalledWith('ts-1', { limit: 1 });
    expect(screen.getByRole('alert')).toHaveTextContent(
      /This needs 20 .+, but your organization has 10 left for this period\./
    );
  });

  it("keeps Run enabled when the run's tests exactly fit", async () => {
    mockTestSetTestCount = 20;
    mockExecutionUsage(usageItem(80, 100));
    renderRunDrawer();

    await waitFor(() => expect(mockGetTestSetTests).toHaveBeenCalled());
    // Let the fetched count land, so the gate is judging 20 tests, not 1.
    await act(async () => {});
    expect(screen.getByRole('button', { name: /re-run tests/i })).toBeEnabled();
  });
});

function renderExecuteDrawer() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RunDrawer
        open
        onClose={jest.fn()}
        mode="executeTestSet"
        data={{ testSetId: 'ts-1' }}
      />
    </QueryClientProvider>
  );
}

describe('RunDrawer sections', () => {
  beforeEach(() => mockExecutionUsage(usageItem(0, 100)));
  afterEach(() => jest.clearAllMocks());

  it('groups the fields into five sections', async () => {
    renderExecuteDrawer();

    for (const name of [
      'What to run',
      'Run against',
      'Scoring',
      'When',
      'More options',
    ]) {
      expect(
        screen.getByRole('button', { name: new RegExp(name) })
      ).toBeVisible();
    }
    await waitFor(() =>
      expect(screen.getByLabelText('Test Set')).toHaveValue('Safety checks')
    );
  });

  it('shows a folded section as one summary line', () => {
    renderExecuteDrawer();

    const moreOptions = screen.getByRole('button', { name: /more options/i });
    expect(moreOptions).toHaveAttribute('aria-expanded', 'false');
    expect(
      within(moreOptions).getByText('Parallel · preflight on')
    ).toBeInTheDocument();

    fireEvent.click(moreOptions);
    expect(moreOptions).toHaveAttribute('aria-expanded', 'true');
    expect(within(moreOptions).queryByText(/preflight on/)).toBeNull();
  });

  it('turns the drawer into a schedule when "Repeat" is picked', async () => {
    renderExecuteDrawer();

    expect(screen.getByTestId('footer-summary')).toHaveTextContent(/1 run/);
    fireEvent.click(screen.getByRole('button', { name: 'Repeat' }));

    expect(
      screen.getByRole('heading', { name: 'Schedule Test Set' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Schedule Run' })
    ).toBeInTheDocument();
    expect(screen.getByTestId('footer-summary')).toHaveTextContent(
      'Creates 1 schedule'
    );
    expect(
      screen.getByText("Schedules don't keep test run tags.")
    ).toBeInTheDocument();
  });

  it('hides "Only tests tagged" when the tests carry no tags', async () => {
    mockTestSetTestTags = [];
    renderExecuteDrawer();

    await waitFor(() => expect(mockGetTestSetTestTags).toHaveBeenCalled());
    expect(screen.queryByLabelText('Only tests tagged')).toBeNull();
  });

  it('counts only the tagged tests once a tag is picked', async () => {
    mockTestSetTestTags = [
      { name: 'billing', test_count: 2 },
      { name: 'smoke', test_count: 5 },
    ];
    renderExecuteDrawer();

    const field = await screen.findByLabelText('Only tests tagged');
    fireEvent.mouseDown(field);
    fireEvent.click(await screen.findByRole('option', { name: /smoke/ }));

    await waitFor(() =>
      expect(mockGetTestSetTests).toHaveBeenLastCalledWith(
        expect.any(String),
        expect.objectContaining({
          $filter: "(_tags_relationship/any(t: t/tag/name eq 'smoke'))",
        })
      )
    );
    expect(screen.getByLabelText('Test Set')).toHaveValue('Safety checks');
    const whatToRun = screen.getByRole('button', { name: /what to run/i });
    fireEvent.click(whatToRun);
    expect(
      within(whatToRun).getByText('Safety checks · tests tagged smoke')
    ).toBeInTheDocument();
    mockTestSetTestTags = [];
  });

  it('offers only the tags every selected test set carries', async () => {
    mockGetTestSetTestTags.mockImplementation(id =>
      Promise.resolve(
        id === 'ts-1'
          ? [
              { name: 'billing', test_count: 2 },
              { name: 'smoke', test_count: 5 },
            ]
          : [{ name: 'smoke', test_count: 1 }]
      )
    );
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <RunDrawer
          open
          onClose={jest.fn()}
          mode="createFromGrid"
          data={{ selectedTestSetIds: ['ts-1', 'ts-2'] }}
        />
      </QueryClientProvider>
    );

    fireEvent.mouseDown(await screen.findByLabelText('Only tests tagged'));
    const options = await screen.findAllByRole('option');
    expect(options.map(o => o.textContent)).toEqual(['smoke6 tests']);
    mockGetTestSetTestTags.mockImplementation(() =>
      Promise.resolve(mockTestSetTestTags)
    );
  });

  it('runs every test set carrying a tag, now', async () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <RunDrawer open onClose={jest.fn()} mode="newTestRun" />
      </QueryClientProvider>
    );

    expect(screen.getByRole('button', { name: 'When' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sets with a tag' }));
    expect(screen.queryByRole('button', { name: 'When' })).toBeNull();

    fireEvent.mouseDown(await screen.findByLabelText(/Test set tag/));
    fireEvent.click(await screen.findByRole('option', { name: 'nightly' }));

    expect(
      await screen.findByText('2 test sets: Billing, Claims')
    ).toBeInTheDocument();
    const whatToRun = screen.getByRole('button', { name: /what to run/i });
    fireEvent.click(whatToRun);
    expect(
      within(whatToRun).getByText('Sets tagged nightly · 2 test sets')
    ).toBeInTheDocument();
  });

  it('names the one test set picked in the list', async () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <RunDrawer
          open
          onClose={jest.fn()}
          mode="createFromGrid"
          data={{ selectedTestSetIds: ['ts-1'] }}
        />
      </QueryClientProvider>
    );

    await waitFor(() =>
      expect(screen.getByLabelText('Test Set')).toHaveValue('Safety checks')
    );
  });
});
