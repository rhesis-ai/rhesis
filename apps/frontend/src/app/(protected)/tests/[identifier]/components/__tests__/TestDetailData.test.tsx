import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import type { UUID } from 'crypto';
import TestDetailData from '../TestDetailData';
import { TestDetail } from '@/utils/api-client/interfaces/tests';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

// ---- Navigation ----

const mockRefresh = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: mockRefresh }),
  usePathname: () => '/tests/t-1',
  useSearchParams: () => new URLSearchParams(),
}));

// ---- Notifications ----

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

// ---- API client ----

const mockGetBehaviors = jest.fn();
const mockGetTopics = jest.fn();
const mockGetCategories = jest.fn();
const mockGetTypeLookups = jest.fn();
const mockUpdateTest = jest.fn();
const mockGetTest = jest.fn();
const mockGetPrompt = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getBehaviorClient: () => ({ getBehaviors: mockGetBehaviors }),
    getTypeLookupClient: () => ({ getTypeLookups: mockGetTypeLookups }),
    getTopicClient: () => ({ getTopics: mockGetTopics }),
    getCategoryClient: () => ({ getCategories: mockGetCategories }),
    getTestsClient: () => ({
      getTest: mockGetTest,
      updateTest: mockUpdateTest,
    }),
    getPromptsClient: () => ({ getPrompt: mockGetPrompt }),
  })),
}));

// ---- Sub-component stubs ----
// Stub heavy sub-components to keep tests focused on TestDetailData logic.

jest.mock('../TestExecutableField', () => ({
  __esModule: true,
  default: ({
    initialContent,
    fieldName,
  }: {
    initialContent: string;
    fieldName?: string;
  }) => (
    <div
      data-testid={
        fieldName === 'expected_response' ? 'expected-response' : 'test-prompt'
      }
    >
      {initialContent}
    </div>
  ),
}));

jest.mock('../MultiTurnConfigFields', () => ({
  __esModule: true,
  default: () => <div data-testid="multi-turn-config" />,
}));

jest.mock('@/components/common/BaseFreesoloAutocomplete', () => ({
  __esModule: true,
  default: ({
    label,
    value,
    onChange,
    options,
  }: {
    label: string;
    value: string;
    onChange: (v: unknown) => void;
    options: Array<{ id: string; name: string }>;
  }) => (
    <select
      aria-label={label}
      value={value}
      onChange={e => {
        const opt = options.find(o => o.name === e.target.value);
        onChange(opt ?? e.target.value);
      }}
    >
      <option value="">(none)</option>
      {options.map(o => (
        <option key={o.id} value={o.name}>
          {o.name}
        </option>
      ))}
    </select>
  ),
}));

jest.mock('@/components/common/FilePreview', () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => (
    <div data-testid="file-preview">{title}</div>
  ),
}));

jest.mock('../MultiTurnConfigFields', () => ({
  __esModule: true,
  default: () => <div data-testid="multi-turn-config" />,
}));

// ---- Fixtures ----

const makeTest = (overrides: Partial<TestDetail> = {}): TestDetail => ({
  id: u(1),
  prompt_id: u(2),
  prompt: {
    id: u(2),
    content: 'Is this safe?',
    expected_response: 'Yes, it is safe.',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    language_code: 'en',
  },
  behavior: { id: u(3), name: 'Safety' },
  topic: { id: u(4), name: 'Topic A' },
  category: { id: u(5), name: 'Cat 1' },
  test_type: { id: u(6), type_name: 'Adversarial', type_value: 'adversarial' },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

// ---- Tests ----

describe('TestDetailData', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetBehaviors.mockResolvedValue([
      { id: 'b-1', name: 'Safety' },
      { id: 'b-2', name: 'Accuracy' },
    ]);
    mockGetTypeLookups.mockResolvedValue([
      { id: 'tt-1', type_value: 'adversarial' },
    ]);
    mockGetTopics.mockResolvedValue([{ id: 'tp-1', name: 'Topic A' }]);
    mockGetCategories.mockResolvedValue([{ id: 'cat-1', name: 'Cat 1' }]);
    mockGetTest.mockResolvedValue(makeTest());
    mockGetPrompt.mockResolvedValue({
      content: 'Is this safe?',
      expected_response: 'Yes.',
    });
    mockUpdateTest.mockResolvedValue({});
  });

  it('renders the test prompt content', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() =>
      expect(screen.getByTestId('test-prompt')).toBeInTheDocument()
    );
    expect(screen.getByTestId('test-prompt')).toHaveTextContent(
      'Is this safe?'
    );
  });

  it('renders the expected response content', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() =>
      expect(screen.getByTestId('expected-response')).toBeInTheDocument()
    );
    expect(screen.getByTestId('expected-response')).toHaveTextContent(
      'Yes, it is safe.'
    );
  });

  it('renders the read-only Type field', () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    expect(screen.getByLabelText('Type')).toHaveValue('adversarial');
  });

  it('renders the read-only Created date field', () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    expect(screen.getByLabelText('Created')).toBeInTheDocument();
  });

  it('fetches and populates behavior options on mount', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() => expect(mockGetBehaviors).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'Accuracy' })
      ).toBeInTheDocument()
    );
  });

  it('shows the current behavior value once options are loaded', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    // Wait until 'Safety' appears as an option in the dropdown
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Safety' })).toBeInTheDocument()
    );
    expect(screen.getByLabelText('Behavior')).toHaveValue('Safety');
  });

  it('calls updateTest with behavior_id when a behavior is selected', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'Accuracy' })
      ).toBeInTheDocument()
    );

    await userEvent.selectOptions(
      screen.getByLabelText('Behavior'),
      'Accuracy'
    );

    await waitFor(() =>
      expect(mockUpdateTest).toHaveBeenCalledWith(u(1), {
        behavior_id: 'b-2',
      })
    );
  });

  it('shows success notification after behavior update', async () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'Accuracy' })
      ).toBeInTheDocument()
    );

    await userEvent.selectOptions(
      screen.getByLabelText('Behavior'),
      'Accuracy'
    );

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('behavior'),
        expect.objectContaining({ severity: 'success' })
      )
    );
  });

  it('shows error notification when updateTest fails', async () => {
    mockUpdateTest.mockRejectedValue(new Error('Server error'));
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'Accuracy' })
      ).toBeInTheDocument()
    );

    await userEvent.selectOptions(
      screen.getByLabelText('Behavior'),
      'Accuracy'
    );

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        expect.objectContaining({ severity: 'error' })
      )
    );
  });

  it('renders sources when test_metadata has sources', () => {
    const test = makeTest({
      test_metadata: {
        sources: [{ name: 'Doc A', content: 'content here' }],
      },
    });
    render(<TestDetailData sessionToken="tok" test={test} />);
    expect(screen.getByTestId('file-preview')).toBeInTheDocument();
    expect(screen.getByTestId('file-preview')).toHaveTextContent('Doc A');
  });

  it('does not render sources section when no sources', () => {
    render(<TestDetailData sessionToken="tok" test={makeTest()} />);
    expect(screen.queryByTestId('file-preview')).not.toBeInTheDocument();
  });
});
