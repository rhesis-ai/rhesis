import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestSetDetailsSection from '../TestSetDetailsSection';
import { TestSet } from '@/utils/api-client/interfaces/test-set';

// ---- Auth ----

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

// ---- API client ----

const mockUpdateTestSet = jest.fn();
const mockDownloadTestSet = jest.fn();
const mockPreviewSync = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestSetsClient: () => ({
      updateTestSet: mockUpdateTestSet,
      downloadTestSet: mockDownloadTestSet,
    }),
    getGarakClient: () => ({
      previewSync: mockPreviewSync,
    }),
  })),
}));

// ---- Sub-component stubs ----

jest.mock('../ExecuteTestSetDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="execute-drawer" /> : null,
}));

jest.mock('../TestSetTags', () => ({
  __esModule: true,
  default: () => <div data-testid="test-set-tags" />,
}));

jest.mock('../TestSetMetrics', () => ({
  __esModule: true,
  default: () => <div data-testid="test-set-metrics" />,
}));

// ---- Fixtures ----

const makeTestSet = (overrides: Partial<TestSet> = {}): TestSet => ({
  id: 'ts-1',
  name: 'My Test Set',
  description: 'A description of the test set.',
  owner: { id: 'u1', name: 'Alice', email: 'alice@example.com' },
  user: { id: 'u1', name: 'Alice', email: 'alice@example.com' },
  test_set_type: { type_value: 'evaluation' },
  attributes: {
    metadata: {
      total_tests: 5,
      behaviors: [],
      categories: [],
      topics: [],
      sources: [],
    },
  },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-15T10:00:00Z',
  updated_at: '2024-01-15T10:00:00Z',
  ...overrides,
});

// ---- Tests ----

describe('TestSetDetailsSection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUpdateTestSet.mockResolvedValue({});
    mockDownloadTestSet.mockResolvedValue(
      new Blob(['csv data'], { type: 'text/csv' })
    );
  });

  it('renders the test set name', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(screen.getByText('My Test Set')).toBeInTheDocument();
  });

  it('renders the description text', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(
      screen.getByText('A description of the test set.')
    ).toBeInTheDocument();
  });

  it('renders "Execute Test Set" button enabled when tests > 0', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(
      screen.getByRole('button', { name: /execute test set/i })
    ).not.toBeDisabled();
  });

  it('disables "Execute Test Set" when total_tests is 0', () => {
    const testSet = makeTestSet({
      attributes: {
        metadata: {
          total_tests: 0,
          behaviors: [],
          categories: [],
          topics: [],
          sources: [],
        },
      },
    });
    render(<TestSetDetailsSection testSet={testSet} sessionToken="tok" />);
    expect(
      screen.getByRole('button', { name: /execute test set/i })
    ).toBeDisabled();
  });

  it('opens ExecuteTestSetDrawer on "Execute Test Set" click', async () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    await userEvent.click(
      screen.getByRole('button', { name: /execute test set/i })
    );
    expect(screen.getByTestId('execute-drawer')).toBeInTheDocument();
  });

  it('renders "Download Test Set" button', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(
      screen.getByRole('button', { name: /download test set/i })
    ).toBeInTheDocument();
  });

  it('renders the test set type chip', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(screen.getByText('evaluation')).toBeInTheDocument();
  });

  it('renders creator name', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('shows Edit button for description', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    // Both title and description have Edit buttons
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
  });

  describe('edit description', () => {
    it('switches to edit mode when description Edit is clicked', async () => {
      render(
        <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
      );
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      // The description edit button is the second one (after title)
      await userEvent.click(editButtons[editButtons.length - 1]);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('calls updateTestSet with new description on Confirm', async () => {
      render(
        <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
      );
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      await userEvent.click(editButtons[editButtons.length - 1]);

      const textarea = screen.getByRole('textbox');
      await userEvent.clear(textarea);
      await userEvent.type(textarea, 'Updated description');
      await userEvent.click(screen.getByRole('button', { name: /confirm/i }));

      await waitFor(() =>
        expect(mockUpdateTestSet).toHaveBeenCalledWith('ts-1', {
          description: 'Updated description',
        })
      );
    });

    it('cancels edit without calling API on Cancel', async () => {
      render(
        <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
      );
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      await userEvent.click(editButtons[editButtons.length - 1]);
      await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
      expect(mockUpdateTestSet).not.toHaveBeenCalled();
    });
  });

  it('renders TestSetTags and TestSetMetrics sub-components', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(screen.getByTestId('test-set-tags')).toBeInTheDocument();
    expect(screen.getByTestId('test-set-metrics')).toBeInTheDocument();
  });

  it('does not show Garak sync button for non-Garak test sets', () => {
    render(
      <TestSetDetailsSection testSet={makeTestSet()} sessionToken="tok" />
    );
    expect(
      screen.queryByRole('button', { name: /sync from garak/i })
    ).not.toBeInTheDocument();
  });

  it('shows Garak sync button for Garak-imported test sets', () => {
    const garakTestSet = makeTestSet({
      attributes: {
        source: 'garak',
        garak_version: '0.1.0',
        garak_modules: ['lmrc'],
        metadata: {
          total_tests: 5,
          behaviors: [],
          categories: [],
          topics: [],
          sources: [],
        },
      },
    });
    render(<TestSetDetailsSection testSet={garakTestSet} sessionToken="tok" />);
    expect(
      screen.getByRole('button', { name: /sync from garak/i })
    ).toBeInTheDocument();
  });
});
