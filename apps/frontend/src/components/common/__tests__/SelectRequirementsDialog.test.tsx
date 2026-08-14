import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SelectRequirementsDialog from '../SelectRequirementsDialog';
import { RequirementClient } from '@/utils/api-client/requirement-client';

jest.mock('@/utils/api-client/requirement-client');

const STABLE_EMPTY_IDS: never[] = [];

function makeRequirement(overrides: Record<string, unknown> = {}) {
  return {
    id: 'requirement-1',
    name: 'Safety',
    description: 'Checks for harmful content',
    metrics: [],
    ...overrides,
  };
}

let mockGetRequirements: jest.Mock;

beforeEach(() => {
  mockGetRequirements = jest.fn().mockResolvedValue([]);
  (RequirementClient as jest.Mock).mockImplementation(() => ({
    getRequirementsWithMetrics: mockGetRequirements,
  }));
});

afterEach(() => {
  jest.clearAllMocks();
});

function renderDialog(
  props: Partial<React.ComponentProps<typeof SelectRequirementsDialog>> = {}
) {
  const defaults = {
    open: true,
    onClose: jest.fn(),
    onSelect: jest.fn(),
    excludeRequirementIds: STABLE_EMPTY_IDS,
  };
  return render(<SelectRequirementsDialog {...defaults} {...props} />);
}

describe('SelectRequirementsDialog', () => {
  it('shows a loading indicator while fetching requirements', async () => {
    mockGetRequirements.mockImplementation(() => new Promise(() => {}));
    renderDialog();
    expect(screen.getByText(/loading requirements/i)).toBeInTheDocument();
  });

  it('renders the dialog with a title', async () => {
    renderDialog();
    await screen.findByRole('dialog');
    expect(screen.getByText('Add to Requirement')).toBeInTheDocument();
  });

  it('shows "No requirements available" when the API returns an empty list', async () => {
    mockGetRequirements.mockResolvedValue([]);
    renderDialog();
    await screen.findByText(/no requirements available/i);
  });

  it('renders a list of requirements after loading', async () => {
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'b-1', name: 'Coherence' }),
      makeRequirement({ id: 'b-2', name: 'Safety' }),
    ]);
    renderDialog();
    await screen.findByText('Coherence');
    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('renders requirement descriptions when present', async () => {
    mockGetRequirements.mockResolvedValue([
      makeRequirement({
        id: 'b-1',
        name: 'Safety',
        description: 'Prevents harmful output',
      }),
    ]);
    renderDialog();
    await screen.findByText('Prevents harmful output');
  });

  it('shows metric count chip when a requirement has metrics', async () => {
    mockGetRequirements.mockResolvedValue([
      makeRequirement({
        id: 'b-1',
        name: 'Safety',
        metrics: [{ id: 'm-1' }, { id: 'm-2' }],
      }),
    ]);
    renderDialog();
    await screen.findByText('2 Metrics');
  });

  it('shows "1 Metric" (singular) when a requirement has exactly one metric', async () => {
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'b-1', name: 'Safety', metrics: [{ id: 'm-1' }] }),
    ]);
    renderDialog();
    await screen.findByText('1 Metric');
  });

  it('excludes already-selected requirements from the list', async () => {
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'excluded-id', name: 'Already Added' }),
      makeRequirement({ id: 'available-id', name: 'Available Requirement' }),
    ]);
    renderDialog({ excludeRequirementIds: ['excluded-id' as never] });
    await screen.findByText('Available Requirement');
    expect(screen.queryByText('Already Added')).not.toBeInTheDocument();
  });

  it('shows an error message when the fetch fails', async () => {
    mockGetRequirements.mockRejectedValue(new Error('Failed to load'));
    renderDialog();
    await screen.findByText('Failed to load');
  });

  it('filters requirements by search query (name match)', async () => {
    const user = userEvent.setup();
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'b-1', name: 'Safety' }),
      makeRequirement({ id: 'b-2', name: 'Coherence' }),
    ]);
    renderDialog();
    await screen.findByText('Safety');

    await user.type(
      screen.getByPlaceholderText(/search requirements/i),
      'safe'
    );

    expect(screen.queryByText('Coherence')).not.toBeInTheDocument();
    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('filters requirements by search query (description match)', async () => {
    const user = userEvent.setup();
    mockGetRequirements.mockResolvedValue([
      makeRequirement({
        id: 'b-1',
        name: 'Alpha',
        description: 'detects bias',
      }),
      makeRequirement({
        id: 'b-2',
        name: 'Beta',
        description: 'checks safety',
      }),
    ]);
    renderDialog();
    await screen.findByText('Alpha');

    await user.type(
      screen.getByPlaceholderText(/search requirements/i),
      'bias'
    );

    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
  });

  it('shows "No requirements match your search" when search yields no results', async () => {
    const user = userEvent.setup();
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'b-1', name: 'Safety' }),
    ]);
    renderDialog();
    await screen.findByText('Safety');

    await user.type(
      screen.getByPlaceholderText(/search requirements/i),
      'zzznomatch'
    );

    await screen.findByText(/no requirements match your search/i);
  });

  it('calls onSelect with the requirement id and closes when a requirement is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const onClose = jest.fn();
    mockGetRequirements.mockResolvedValue([
      makeRequirement({ id: 'requirement-xyz', name: 'Relevance' }),
    ]);
    renderDialog({ onSelect, onClose });
    await screen.findByText('Relevance');

    await user.click(screen.getByText('Relevance'));

    expect(onSelect).toHaveBeenCalledWith('requirement-xyz');
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

  it('fetches requirements when dialog opens', async () => {
    mockGetRequirements.mockResolvedValue([]);
    renderDialog({ open: true });
    await waitFor(() => {
      expect(mockGetRequirements).toHaveBeenCalledTimes(1);
    });
  });

  it('does not fetch requirements when dialog is closed', () => {
    renderDialog({ open: false });
    expect(mockGetRequirements).not.toHaveBeenCalled();
  });
});
