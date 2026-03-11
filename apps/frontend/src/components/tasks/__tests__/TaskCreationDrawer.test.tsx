import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TaskCreationDrawer } from '../TaskCreationDrawer';

jest.mock('@/components/common/BaseDrawer', () => ({
  __esModule: true,
  default: ({
    open,
    children,
    onClose,
    onSave,
    saveButtonText,
    title,
  }: {
    open: boolean;
    children: React.ReactNode;
    onClose: () => void;
    onSave: () => void;
    saveButtonText?: string;
    title: string;
    loading?: boolean;
    width?: number;
  }) =>
    open ? (
      <div data-testid="base-drawer">
        <h2>{title}</h2>
        {children}
        <button onClick={onClose}>close-drawer</button>
        <button onClick={onSave}>{saveButtonText || 'Save'}</button>
      </div>
    ) : null,
}));

jest.mock('@/utils/task-lookup', () => ({
  getPriorities: jest.fn().mockResolvedValue([
    { id: 'p1', type_name: 'TaskPriority', type_value: 'Low', description: '' },
    {
      id: 'p2',
      type_name: 'TaskPriority',
      type_value: 'High',
      description: '',
    },
  ]),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsersClient: () => ({
      getUsers: jest.fn().mockResolvedValue({
        data: [
          { id: 'u1', name: 'Alice' },
          { id: 'u2', name: 'Bob' },
        ],
      }),
    }),
  })),
}));

jest.mock('@/utils/entity-helpers', () => ({
  getEntityDisplayName: (t: string) => t,
}));

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({
    data: { session_token: 'test-tok' },
    status: 'authenticated',
  })),
}));

const DEFAULT_PROPS = {
  open: true,
  onClose: jest.fn(),
  onSubmit: jest.fn().mockResolvedValue(undefined),
  entityType: 'Test' as const,
  entityId: 'e1',
  currentUserId: 'u1',
  currentUserName: 'Alice',
};

describe('TaskCreationDrawer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    DEFAULT_PROPS.onClose = jest.fn();
    DEFAULT_PROPS.onSubmit = jest.fn().mockResolvedValue(undefined);
  });

  it('does not render when open=false', () => {
    render(<TaskCreationDrawer {...DEFAULT_PROPS} open={false} />);
    expect(screen.queryByTestId('base-drawer')).not.toBeInTheDocument();
  });

  it('renders the drawer when open=true', () => {
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('base-drawer')).toBeInTheDocument();
  });

  it('renders the title input field', () => {
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/task title/i)).toBeInTheDocument();
  });

  it('renders the description field', () => {
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
  });

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup();
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);

    await user.click(screen.getByRole('button', { name: 'close-drawer' }));
    expect(DEFAULT_PROPS.onClose).toHaveBeenCalled();
  });

  it('calls onSubmit with title and entity data when form is submitted with valid title', async () => {
    const user = userEvent.setup();
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);

    await user.type(screen.getByLabelText(/task title/i), 'My New Task');

    const submitBtn = screen.getByRole('button', { name: /create task/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(DEFAULT_PROPS.onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'My New Task',
          entity_type: 'Test',
          entity_id: 'e1',
        })
      );
    });
  });

  it('does NOT call onSubmit when title is empty', async () => {
    const user = userEvent.setup();
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);

    const submitBtn = screen.getByRole('button', { name: /create task/i });
    await user.click(submitBtn);

    expect(DEFAULT_PROPS.onSubmit).not.toHaveBeenCalled();
  });

  it('resets the form after successful submission', async () => {
    const user = userEvent.setup();
    render(<TaskCreationDrawer {...DEFAULT_PROPS} />);

    const titleInput = screen.getByLabelText(/task title/i);
    await user.type(titleInput, 'Task to reset');
    await user.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => expect(titleInput).toHaveValue(''));
  });
});
