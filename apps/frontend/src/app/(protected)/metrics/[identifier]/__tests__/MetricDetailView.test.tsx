import React from 'react';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
  act,
} from '@testing-library/react';
import '@testing-library/jest-dom';
import { MetricDetailView } from '../MetricDetailView';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';

const mockGetMetric = jest.fn();
const mockUpdateMetric = jest.fn();
const mockGetModels = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricsClient: () => ({
      getMetric: mockGetMetric,
      updateMetric: mockUpdateMetric,
    }),
    getModelsClient: () => ({
      getModels: mockGetModels,
    }),
  })),
}));

jest.mock('@/utils/api-client/tags-client', () => ({
  TagsClient: jest.fn().mockImplementation(() => ({
    assignTagToEntity: jest.fn(),
    removeTagFromEntity: jest.fn(),
  })),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

// Always allow editing — capability checks are not the focus of this test.
jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: jest.fn(),
}));

jest.mock('@/utils/entity-helpers', () => ({
  generateCopyName: (name: string) => `${name} (copy)`,
}));

const mockMetric = {
  id: 'metric-1',
  name: 'Test Metric',
  description: 'Test description',
  tags: [],
  evaluation_prompt: 'Test prompt',
  evaluation_steps: 'Step 1:\nFirst step\n---\nStep 2:\nSecond step',
  reasoning: 'Test reasoning',
  score_type: 'numeric' as const,
  min_score: 0,
  max_score: 10,
  threshold: 5,
  threshold_operator: '>=' as const,
  explanation: 'Test explanation',
  ground_truth_required: false,
  context_required: false,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  metric_type: { id: 'mt-1', type_name: 'MetricType', type_value: 'numeric' },
  backend_type: { id: 'bt-1', type_name: 'BackendType', type_value: 'rhesis' },
  metric_scope: ['Single-Turn'],
  categories: [],
  passing_categories: [],
  model_id: 'model-1',
} as unknown as MetricDetail;

async function renderAndViewMetric() {
  await act(async () => {
    render(<MetricDetailView metricId="metric-1" />);
  });
  // The component renders `metric.name` in multiple places (breadcrumb label,
  // page heading via PageLayout's title prop, and a Typography in detailBody).
  // Query by role+level to target the unique h1 rendered by PageLayout, which
  // avoids `getByText`'s "Found multiple elements" error while still verifying
  // the metric loaded.
  await waitFor(() =>
    expect(
      screen.getByRole('heading', { name: 'Test Metric', level: 1 })
    ).toBeInTheDocument()
  );
}

function findEvaluationEditButton(): HTMLElement {
  const heading = screen.getByText('Evaluation Process');
  const card = heading.closest('.MuiPaper-root');
  if (!card) {
    throw new Error('Could not find SectionCard Paper for Evaluation Process');
  }
  return within(card as HTMLElement).getByRole('button', { name: /^edit$/i });
}

/**
 * Issue #1045: Evaluation step fields reset on adding new step.
 *
 * Root cause: populateFieldRefs scheduled a setTimeout(0) that captured the
 * original stepsWithIds closure and overwrote the step input DOM values with
 * the original metric content. When the macrotask fired after the user had
 * already typed new text (and often after clicking "Add Step"), the typed text
 * was silently discarded.
 *
 * Fix: the setTimeout block is redundant — defaultValue already seeds the DOM
 * value on mount, and the inputRef callback registers synchronously. Removing
 * the setTimeout eliminates the stale-closure overwrite.
 */
describe('MetricDetailView — evaluation steps (issue #1045)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(mockMetric);
    mockGetModels.mockResolvedValue({ data: [] });
    mockUpdateMetric.mockResolvedValue({});
  });

  it('loads existing step values from the metric when entering edit mode', async () => {
    await renderAndViewMetric();

    await act(async () => {
      fireEvent.click(findEvaluationEditButton());
    });

    const firstStep = screen.getByPlaceholderText(
      /Step 1: Describe this evaluation step/i
    );
    expect(firstStep).toHaveValue('First step');

    const secondStep = screen.getByPlaceholderText(
      /Step 2: Describe this evaluation step/i
    );
    expect(secondStep).toHaveValue('Second step');
  });

  it('preserves evaluation step text when adding a new step (issue #1045)', async () => {
    await renderAndViewMetric();

    // Enter edit mode — this is where the buggy setTimeout(0) was scheduled.
    await act(async () => {
      fireEvent.click(findEvaluationEditButton());
    });

    const firstStep = screen.getByPlaceholderText(
      /Step 1: Describe this evaluation step/i
    );

    // Simulate the user typing new text into the first step.
    fireEvent.change(firstStep, { target: { value: 'my edited text' } });
    expect(firstStep).toHaveValue('my edited text');

    // Click "Add Step" — this is the action that triggered the reset in #1045.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /add step/i }));
    });

    // Yield to the event loop so any pending setTimeout(0) macrotask fires.
    // With the bug present, this is where the stale closure overwrites the
    // user's typed text with the original metric content.
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    expect(firstStep).toHaveValue('my edited text');
  });

  it('preserves evaluation step text when removing a step', async () => {
    await renderAndViewMetric();

    await act(async () => {
      fireEvent.click(findEvaluationEditButton());
    });

    const firstStep = screen.getByPlaceholderText(
      /Step 1: Describe this evaluation step/i
    );
    fireEvent.change(firstStep, { target: { value: 'edited first step' } });

    // Remove the second step — an adjacent code path that must also preserve
    // the text already entered in the remaining step inputs.
    // IconButton wrapping <DeleteIcon /> has no aria-label (pre-existing a11y
    // debt, out of scope for #1045), so query by icon testid and walk up to
    // the button ancestor.
    const deleteIcons = screen.getAllByTestId('DeleteIcon');
    const deleteButtons = deleteIcons.map(icon => icon.closest('button')!);
    // The second step's delete button is the last one rendered before "Add Step".
    await act(async () => {
      fireEvent.click(deleteButtons[deleteButtons.length - 1]);
    });

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    expect(firstStep).toHaveValue('edited first step');
  });
});
