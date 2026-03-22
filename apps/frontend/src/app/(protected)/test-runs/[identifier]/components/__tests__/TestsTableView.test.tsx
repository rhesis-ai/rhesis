import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestsTableView from '../TestsTableView';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

// ---- Stub heavy child components to avoid cascading dependency issues ----

jest.mock('../TestResultDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../ReviewJudgementDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

// ---- API client: only used in event handlers, not needed for render-path tests ----

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestResultsClient: () => ({ getTestResult: jest.fn() }),
    getStatusClient: () => ({
      getStatuses: jest.fn().mockResolvedValue([]),
    }),
  })),
}));

// ---- Fixtures ----

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

let counter = 0;

const makeResult = (
  overrides: Partial<TestResultDetail> = {}
): TestResultDetail =>
  ({
    id: u(++counter),
    test_configuration_id: u(99),
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    test_metrics: {
      execution_time: 0,
      metrics: {
        accuracy: {
          score: 1,
          reason: '',
          backend: 'test',
          description: '',
          is_successful: true,
        },
      },
    },
    test_output: { output: 'ok', context: [], session_id: 'sess' },
    status: { id: u(10), name: 'Pass' },
    prompt_id: u(20),
    ...overrides,
  }) as unknown as TestResultDetail;

const makeTests = (count: number) =>
  Array.from({ length: count }, () => makeResult());

const defaultProps = {
  prompts: {},
  behaviors: [],
  testRunId: u(1),
  sessionToken: 'tok',
  onTestResultUpdate: jest.fn(),
  currentUserId: 'user-1',
  currentUserName: 'Alice',
};

// ---- Tests ----

describe('TestsTableView — pagination page-reset regression', () => {
  beforeEach(() => {
    counter = 0;
    jest.clearAllMocks();
  });

  it('resets to page 0 when the filtered list shrinks below the current page', async () => {
    const user = userEvent.setup();
    const thirtyTests = makeTests(30);

    const { rerender } = render(
      <TestsTableView tests={thirtyTests} {...defaultProps} />
    );

    // Navigate to page 2 — MUI shows "26–30 of 30"
    await user.click(screen.getByRole('button', { name: /next page/i }));
    await waitFor(() => {
      expect(screen.getByText(/26.+30 of 30/)).toBeInTheDocument();
    });

    // Simulate a filter reducing results to 5 (page 2 no longer exists)
    rerender(
      <TestsTableView tests={thirtyTests.slice(0, 5)} {...defaultProps} />
    );

    // Page should reset to 0 — "1–5 of 5"
    await waitFor(() => {
      expect(screen.getByText(/1.+5 of 5/)).toBeInTheDocument();
    });
  });

  it('stays on the current page when the filtered list still covers it', async () => {
    const user = userEvent.setup();
    const fiftyTests = makeTests(50);

    const { rerender } = render(
      <TestsTableView tests={fiftyTests} {...defaultProps} />
    );

    // Navigate to page 2 — "26–50 of 50"
    await user.click(screen.getByRole('button', { name: /next page/i }));
    await waitFor(() => {
      expect(screen.getByText(/26.+50 of 50/)).toBeInTheDocument();
    });

    // Reduce to 30 — page 2 (offset 25-29) is still valid (maxPage = 1, page = 1)
    rerender(
      <TestsTableView tests={fiftyTests.slice(0, 30)} {...defaultProps} />
    );

    // Should stay on page 2 — "26–30 of 30"
    await waitFor(() => {
      expect(screen.getByText(/26.+30 of 30/)).toBeInTheDocument();
    });
  });

  it('does not override the deep-link page set by initialSelectedTestId on mount', async () => {
    // tests[26] is the 27th test — page 2 (0-indexed page 1) with 25 rows/page
    const thirtyTests = makeTests(30);
    const deepLinkedId = thirtyTests[26].id;

    render(
      <TestsTableView
        tests={thirtyTests}
        initialSelectedTestId={deepLinkedId}
        {...defaultProps}
      />
    );

    // The initialSelectedTestId effect sets page to 1.
    // The out-of-range guard runs with the initial page=0: 0 > maxPage(1) is false,
    // so it does NOT reset. After the page becomes 1, 1 > 1 is also false — no reset.
    await waitFor(() => {
      expect(screen.getByText(/26.+30 of 30/)).toBeInTheDocument();
    });
  });
});
