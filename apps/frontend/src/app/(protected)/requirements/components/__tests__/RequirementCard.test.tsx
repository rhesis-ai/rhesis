import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import RequirementCard, {
  impactColor,
  requirementCardSlots,
} from '../RequirementCard';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';

const mockDeleteRequirement = jest.fn().mockResolvedValue(undefined);

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: (_subject: unknown, _capability: string) => true,
}));

jest.mock('@/utils/api-client/requirement-client', () => ({
  RequirementClient: jest.fn().mockImplementation(() => ({
    deleteRequirement: mockDeleteRequirement,
  })),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/components/common/EntityCard', () => ({
  __esModule: true,
  default: ({
    title,
    description,
    onDelete,
  }: {
    title: string;
    description: string;
    onDelete?: () => void;
  }) => (
    <div data-testid="entity-card">
      <h3>{title}</h3>
      <p>{description}</p>
      {onDelete && (
        <button aria-label="delete requirement" onClick={onDelete}>
          delete
        </button>
      )}
    </div>
  ),
}));

jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: ({
    open,
    onConfirm,
    onClose,
    isLoading,
  }: {
    open: boolean;
    onConfirm: () => void;
    onClose: () => void;
    isLoading?: boolean;
  }) =>
    open ? (
      <div data-testid="delete-modal">
        <button onClick={onConfirm} disabled={isLoading}>
          confirm-delete
        </button>
        <button onClick={onClose}>cancel-delete</button>
      </div>
    ) : null,
}));

function makeRequirement(overrides = {}): RequirementWithMetrics {
  return {
    id: 'b1',
    name: 'Jailbreak Detection',
    description: 'Detects jailbreak attempts',
    organization_id: 'org-1',
    status_id: 'status-1',
    organization: {
      id: 'org-1',
      name: 'Test Org',
      description: '',
      email: 'org@test.com',
      user_id: 'u1',
      tags: [],
    },
    metrics: [],
    ...overrides,
  } as unknown as RequirementWithMetrics;
}

const DEFAULT_PROPS = {
  requirement: makeRequirement(),
  onRefresh: jest.fn(),
};

function renderCard(props = DEFAULT_PROPS) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <RequirementCard {...props} />
    </ThemeProvider>
  );
}

describe('RequirementCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the requirement name', () => {
    renderCard();
    expect(screen.getByText('Jailbreak Detection')).toBeInTheDocument();
  });

  it('renders the requirement description', () => {
    renderCard();
    expect(screen.getByText('Detects jailbreak attempts')).toBeInTheDocument();
  });

  it('shows delete button when there are no metrics', () => {
    renderCard();
    expect(
      screen.getByRole('button', { name: /delete requirement/i })
    ).toBeInTheDocument();
  });

  it('hides delete button when there are metrics (canDelete=false)', () => {
    renderCard({
      ...DEFAULT_PROPS,
      requirement: makeRequirement({
        metrics: [{ id: 'm1', name: 'Metric A' }],
      }),
    });
    expect(
      screen.queryByRole('button', { name: /delete requirement/i })
    ).not.toBeInTheDocument();
  });

  it('opens delete modal when delete button is clicked', async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(
      screen.getByRole('button', { name: /delete requirement/i })
    );
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls deleteRequirement and onRefresh when delete is confirmed', async () => {
    const user = userEvent.setup();
    const onRefresh = jest.fn();
    renderCard({ ...DEFAULT_PROPS, onRefresh });

    await user.click(
      screen.getByRole('button', { name: /delete requirement/i })
    );
    await user.click(screen.getByRole('button', { name: /confirm-delete/i }));

    await waitFor(() => {
      expect(mockDeleteRequirement).toHaveBeenCalledWith('b1');
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('closes delete modal when cancel is clicked', async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(
      screen.getByRole('button', { name: /delete requirement/i })
    );
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /cancel-delete/i }));
    expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
  });

  it('does not render edit, duplicate, view metrics or add metric icons', () => {
    renderCard();

    expect(
      screen.queryByRole('button', { name: /edit requirement/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /duplicate requirement/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /view metrics/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /add metric/i })
    ).not.toBeInTheDocument();
  });
});

describe('requirementCardSlots', () => {
  it('puts the parent in context and impact as a state', () => {
    const slots = requirementCardSlots(
      makeRequirement({
        impact: {
          id: 'i1',
          type_name: 'RequirementImpact',
          type_value: 'Reputation',
        },
        parent: { id: 'p1', name: 'Reliability' },
        children_count: 1,
      })
    );

    expect(slots.context).toBe('Reliability ›');
    expect(slots.facts).toEqual([
      {
        key: 'impact',
        kind: 'state',
        label: 'Reputation impact',
        color: 'secondary.light',
      },
      { key: 'children', kind: 'plain', label: '1 child' },
    ]);
  });

  it('leaves out what is not set', () => {
    const slots = requirementCardSlots(makeRequirement());

    expect(slots.context).toBeUndefined();
    expect(slots.facts).toEqual([]);
  });

  it('counts metrics, tests, examples and sources, keeping zeros', () => {
    const slots = requirementCardSlots(
      makeRequirement({
        metrics: Array.from({ length: 7 }, (_, i) => ({ id: `m${i}` })),
        test_counts: { total: 1, single_turn: 1, multi_turn: 0 },
        examples_count: 1,
        sources: [],
      })
    );

    expect(
      slots.relations.map(({ count, label }) => `${count} ${label}`)
    ).toEqual(['0 sources', '7 metrics', '1 test', '1 example']);
  });

  it('colours each default impact, and an unknown one orange', () => {
    expect(impactColor('Safety')).toBe('error.main');
    expect(impactColor('Customer experience')).toBe('text.disabled');
    expect(impactColor('Our own impact')).toBe('warning.main');
  });
});
