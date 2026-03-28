import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import BehaviorCard from '../BehaviorCard';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';

const mockDeleteBehavior = jest.fn().mockResolvedValue(undefined);
const mockAddBehaviorToMetric = jest.fn().mockResolvedValue(undefined);

jest.mock('@/utils/api-client/behavior-client', () => ({
  BehaviorClient: jest.fn().mockImplementation(() => ({
    deleteBehavior: mockDeleteBehavior,
  })),
}));

jest.mock('@/utils/api-client/metrics-client', () => ({
  MetricsClient: jest.fn().mockImplementation(() => ({
    addBehaviorToMetric: mockAddBehaviorToMetric,
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
    onClick,
    onDelete,
  }: {
    title: string;
    description: string;
    onClick?: () => void;
    onDelete?: (e: React.MouseEvent) => void;
  }) => (
    <div data-testid="entity-card" onClick={onClick}>
      <h3>{title}</h3>
      <p>{description}</p>
      {onDelete && (
        <button
          aria-label="delete"
          onClick={e => {
            e.stopPropagation();
            onDelete(e);
          }}
        >
          Delete
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

jest.mock('@/components/common/SelectMetricsDialog', () => ({
  __esModule: true,
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="select-metrics-dialog">
        <button onClick={onClose}>close-metrics</button>
      </div>
    ) : null,
}));

function makeBehavior(overrides = {}): BehaviorWithMetrics {
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
  } as unknown as BehaviorWithMetrics;
}

const DEFAULT_PROPS = {
  behavior: makeBehavior(),
  onEdit: jest.fn(),
  onDuplicate: jest.fn(),
  onViewMetrics: jest.fn(),
  onRefresh: jest.fn(),
  sessionToken: 'tok',
};

function renderCard(props = DEFAULT_PROPS) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <BehaviorCard {...props} />
    </ThemeProvider>
  );
}

describe('BehaviorCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the behavior name', () => {
    renderCard();
    expect(screen.getByText('Jailbreak Detection')).toBeInTheDocument();
  });

  it('renders the behavior description', () => {
    renderCard();
    expect(screen.getByText('Detects jailbreak attempts')).toBeInTheDocument();
  });

  it('shows delete button when there are no metrics', () => {
    renderCard();
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('hides delete button when there are metrics (canDelete=false)', () => {
    renderCard({
      ...DEFAULT_PROPS,
      behavior: makeBehavior({ metrics: [{ id: 'm1', name: 'Metric A' }] }),
    });
    expect(
      screen.queryByRole('button', { name: /delete/i })
    ).not.toBeInTheDocument();
  });

  it('opens delete modal when delete button is clicked', async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls deleteBehavior and onRefresh when delete is confirmed', async () => {
    const user = userEvent.setup();
    const onRefresh = jest.fn();
    renderCard({ ...DEFAULT_PROPS, onRefresh });

    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(screen.getByRole('button', { name: /confirm-delete/i }));

    await waitFor(() => {
      expect(mockDeleteBehavior).toHaveBeenCalledWith('b1');
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('closes delete modal when cancel is clicked', async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /cancel-delete/i }));
    expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
  });

  it('calls onEdit when the card is clicked', async () => {
    const user = userEvent.setup();
    const onEdit = jest.fn();
    renderCard({ ...DEFAULT_PROPS, onEdit });

    await user.click(screen.getByTestId('entity-card'));
    expect(onEdit).toHaveBeenCalled();
  });
});
