import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SelectBehaviorsDialog from '../SelectBehaviorsDialog';
import { BehaviorClient } from '@/utils/api-client/behavior-client';

jest.mock('@/utils/api-client/behavior-client');

const SESSION_TOKEN = 'test-token';

const STABLE_EMPTY_IDS: never[] = [];

function makeBehavior(overrides: Record<string, unknown> = {}) {
  return {
    id: 'behavior-1',
    name: 'Safety',
    description: 'Checks for harmful content',
    metrics: [],
    ...overrides,
  };
}

let mockGetBehaviors: jest.Mock;

beforeEach(() => {
  mockGetBehaviors = jest.fn().mockResolvedValue([]);
  (BehaviorClient as jest.Mock).mockImplementation(() => ({
    getBehaviorsWithMetrics: mockGetBehaviors,
  }));
});

afterEach(() => {
  jest.clearAllMocks();
});

function renderDialog(
  props: Partial<React.ComponentProps<typeof SelectBehaviorsDialog>> = {}
) {
  const defaults = {
    open: true,
    onClose: jest.fn(),
    onSelect: jest.fn(),
    sessionToken: SESSION_TOKEN,
    excludeBehaviorIds: STABLE_EMPTY_IDS,
  };
  return render(<SelectBehaviorsDialog {...defaults} {...props} />);
}

describe('SelectBehaviorsDialog', () => {
  it('shows a loading indicator while fetching behaviors', async () => {
    mockGetBehaviors.mockImplementation(() => new Promise(() => {}));
    renderDialog();
    expect(screen.getByText(/loading behaviors/i)).toBeInTheDocument();
  });

  it('renders the dialog with a title', async () => {
    renderDialog();
    await screen.findByRole('dialog');
    expect(screen.getByText('Add to Behavior')).toBeInTheDocument();
  });

  it('shows "No behaviors available" when the API returns an empty list', async () => {
    mockGetBehaviors.mockResolvedValue([]);
    renderDialog();
    await screen.findByText(/no behaviors available/i);
  });

  it('renders a list of behaviors after loading', async () => {
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'b-1', name: 'Coherence' }),
      makeBehavior({ id: 'b-2', name: 'Safety' }),
    ]);
    renderDialog();
    await screen.findByText('Coherence');
    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('renders behavior descriptions when present', async () => {
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({
        id: 'b-1',
        name: 'Safety',
        description: 'Prevents harmful output',
      }),
    ]);
    renderDialog();
    await screen.findByText('Prevents harmful output');
  });

  it('shows metric count chip when a behavior has metrics', async () => {
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({
        id: 'b-1',
        name: 'Safety',
        metrics: [{ id: 'm-1' }, { id: 'm-2' }],
      }),
    ]);
    renderDialog();
    await screen.findByText('2 Metrics');
  });

  it('shows "1 Metric" (singular) when a behavior has exactly one metric', async () => {
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'b-1', name: 'Safety', metrics: [{ id: 'm-1' }] }),
    ]);
    renderDialog();
    await screen.findByText('1 Metric');
  });

  it('excludes already-selected behaviors from the list', async () => {
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'excluded-id', name: 'Already Added' }),
      makeBehavior({ id: 'available-id', name: 'Available Behavior' }),
    ]);
    renderDialog({ excludeBehaviorIds: ['excluded-id' as never] });
    await screen.findByText('Available Behavior');
    expect(screen.queryByText('Already Added')).not.toBeInTheDocument();
  });

  it('shows an error message when the fetch fails', async () => {
    mockGetBehaviors.mockRejectedValue(new Error('Failed to load'));
    renderDialog();
    await screen.findByText('Failed to load');
  });

  it('filters behaviors by search query (name match)', async () => {
    const user = userEvent.setup();
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'b-1', name: 'Safety' }),
      makeBehavior({ id: 'b-2', name: 'Coherence' }),
    ]);
    renderDialog();
    await screen.findByText('Safety');

    await user.type(screen.getByPlaceholderText(/search behaviors/i), 'safe');

    expect(screen.queryByText('Coherence')).not.toBeInTheDocument();
    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('filters behaviors by search query (description match)', async () => {
    const user = userEvent.setup();
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'b-1', name: 'Alpha', description: 'detects bias' }),
      makeBehavior({ id: 'b-2', name: 'Beta', description: 'checks safety' }),
    ]);
    renderDialog();
    await screen.findByText('Alpha');

    await user.type(screen.getByPlaceholderText(/search behaviors/i), 'bias');

    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
  });

  it('shows "No behaviors match your search" when search yields no results', async () => {
    const user = userEvent.setup();
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'b-1', name: 'Safety' }),
    ]);
    renderDialog();
    await screen.findByText('Safety');

    await user.type(
      screen.getByPlaceholderText(/search behaviors/i),
      'zzznomatch'
    );

    await screen.findByText(/no behaviors match your search/i);
  });

  it('calls onSelect with the behavior id and closes when a behavior is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const onClose = jest.fn();
    mockGetBehaviors.mockResolvedValue([
      makeBehavior({ id: 'behavior-xyz', name: 'Relevance' }),
    ]);
    renderDialog({ onSelect, onClose });
    await screen.findByText('Relevance');

    await user.click(screen.getByText('Relevance'));

    expect(onSelect).toHaveBeenCalledWith('behavior-xyz');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Cancel is clicked without selecting', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const onClose = jest.fn();
    renderDialog({ onSelect, onClose });
    await screen.findByRole('dialog');

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onClose).toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('fetches behaviors when dialog opens', async () => {
    mockGetBehaviors.mockResolvedValue([]);
    renderDialog({ open: true });
    await waitFor(() => {
      expect(mockGetBehaviors).toHaveBeenCalledTimes(1);
    });
  });

  it('does not fetch behaviors when dialog is closed', () => {
    renderDialog({ open: false });
    expect(mockGetBehaviors).not.toHaveBeenCalled();
  });
});
