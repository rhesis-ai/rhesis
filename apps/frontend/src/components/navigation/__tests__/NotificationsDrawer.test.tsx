import React from 'react';
import { render, screen, waitFor, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import NotificationsDrawer from '../NotificationsDrawer';
import { NotificationSection } from '@/constants/notifications';
import type { Notification } from '@/utils/api-client/notifications-client';

const mockGetNotifications = jest.fn();
const mockMarkRead = jest.fn();
const mockPush = jest.fn();
const mockMarkOneRead = jest.fn();
const mockMarkSectionRead = jest.fn();
let mockUnreadBySection: Record<string, number> = {};

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getNotificationsClient: () => ({
      getNotifications: mockGetNotifications,
      markRead: mockMarkRead,
    }),
  })),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/contexts/NotificationsContext', () => ({
  useNotifications: () => ({
    unreadBySection: mockUnreadBySection,
    markOneRead: mockMarkOneRead,
    markSectionRead: mockMarkSectionRead,
    highlightedIds: () => [],
    clearHighlight: jest.fn(),
    registerViewing: () => () => {},
  }),
}));

function notification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'n-1',
    event_type: 'test_run.execution_completed',
    section: NotificationSection.TEST_RUNS,
    title: 'A run finished',
    body: '3 passed, 1 failed',
    is_failure: false,
    entity_type: 'TestRun',
    entity_id: 'tr-1',
    item_count: 1,
    payload: null,
    read_at: null,
    created_at: new Date().toISOString(),
    project_id: null,
    ...overrides,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockUnreadBySection = {};
  mockGetNotifications.mockResolvedValue([]);
  mockMarkRead.mockResolvedValue({ updated: 1 });
});

describe('NotificationsDrawer', () => {
  it('renders nothing until opened', () => {
    render(<NotificationsDrawer open={false} onClose={jest.fn()} />);
    expect(mockGetNotifications).not.toHaveBeenCalled();
  });

  it('shows an empty state when there is nothing to report', async () => {
    render(<NotificationsDrawer open onClose={jest.fn()} />);
    expect(await screen.findByText('No notifications yet')).toBeInTheDocument();
  });

  it('distinguishes a failed load from an empty inbox', async () => {
    // "No notifications yet" would read as good news when the request failed.
    mockGetNotifications.mockRejectedValue(new Error('network down'));
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    expect(
      await screen.findByText(/Could not load notifications/i)
    ).toBeInTheDocument();
    expect(screen.queryByText('No notifications yet')).not.toBeInTheDocument();
  });

  it('groups rows under a day heading', async () => {
    mockGetNotifications.mockResolvedValue([notification()]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    expect(await screen.findByText('A run finished')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('3 passed, 1 failed')).toBeInTheDocument();
  });

  it('shows how many items a batch row stands for', async () => {
    mockGetNotifications.mockResolvedValue([
      notification({ title: 'Imported test sets', item_count: 3 }),
    ]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    expect(
      await screen.findByText(/Imported test sets \(3\)/)
    ).toBeInTheDocument();
  });

  it('marks a row read through the context, not the client, so the badge follows', async () => {
    // Calling the client directly leaves unreadBySection stale and the bell
    // keeps counting a row the server considers read.
    const onClose = jest.fn();
    mockGetNotifications.mockResolvedValue([notification({ item_count: 3 })]);
    render(<NotificationsDrawer open onClose={onClose} />);

    fireEvent.click(await screen.findByText(/A run finished/));

    expect(mockMarkOneRead).toHaveBeenCalledWith(
      NotificationSection.TEST_RUNS,
      'n-1',
      3
    );
    expect(onClose).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith('/test-runs');
  });

  it('does not re-mark a row that is already read', async () => {
    mockGetNotifications.mockResolvedValue([
      notification({ read_at: new Date().toISOString() }),
    ]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    fireEvent.click(await screen.findByText('A run finished'));

    expect(mockMarkOneRead).not.toHaveBeenCalled();
  });

  it('sends a quota notification to the usage page', async () => {
    mockGetNotifications.mockResolvedValue([
      notification({
        section: NotificationSection.USAGE,
        event_type: 'usage.blocked',
        title: 'Test runs limit reached',
        entity_id: null,
        entity_type: null,
      }),
    ]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    fireEvent.click(await screen.findByText('Test runs limit reached'));

    expect(mockPush).toHaveBeenCalledWith('/organizations/usage');
  });

  it('marks every section with unread items read at once', async () => {
    mockUnreadBySection = {
      [NotificationSection.TEST_RUNS]: 2,
      [NotificationSection.TASKS]: 0,
      [NotificationSection.USAGE]: 1,
    };
    mockGetNotifications.mockResolvedValue([notification()]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    fireEvent.click(
      await screen.findByRole('button', { name: /mark all read/i })
    );

    expect(mockMarkSectionRead).toHaveBeenCalledWith(
      NotificationSection.TEST_RUNS
    );
    expect(mockMarkSectionRead).toHaveBeenCalledWith(NotificationSection.USAGE);
    // A section with nothing unread is not touched.
    expect(mockMarkSectionRead).not.toHaveBeenCalledWith(
      NotificationSection.TASKS
    );
  });

  it('disables mark-all-read when nothing is unread', async () => {
    mockGetNotifications.mockResolvedValue([notification()]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);

    expect(
      await screen.findByRole('button', { name: /mark all read/i })
    ).toBeDisabled();
  });

  it('refetches with the unread filter when it is toggled on', async () => {
    mockGetNotifications.mockResolvedValue([notification()]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);
    await screen.findByText('A run finished');

    fireEvent.click(screen.getByRole('switch', { name: /unread only/i }));

    await waitFor(() =>
      expect(mockGetNotifications).toHaveBeenLastCalledWith(
        expect.objectContaining({ unread_only: true, skip: 0 })
      )
    );
  });

  it('offers older pages only while a full page comes back', async () => {
    mockGetNotifications.mockResolvedValue([notification()]);
    render(<NotificationsDrawer open onClose={jest.fn()} />);
    await screen.findByText('A run finished');

    // One row is a partial page, so there is nothing older to ask for.
    expect(
      screen.queryByRole('button', { name: /load older/i })
    ).not.toBeInTheDocument();
  });

  it('drops a row the next page repeats rather than duplicating a key', async () => {
    // The backend orders by created_at desc with no id tiebreaker, so a
    // notification arriving between pages shifts the window and can re-serve
    // a row already held.
    const firstPage = Array.from({ length: 30 }, (_, i) =>
      notification({ id: `n-${i}`, title: `Row ${i}` })
    );
    mockGetNotifications.mockResolvedValueOnce(firstPage);
    render(<NotificationsDrawer open onClose={jest.fn()} />);
    await screen.findByText('Row 0');

    mockGetNotifications.mockResolvedValueOnce([
      notification({ id: 'n-29', title: 'Row 29' }),
      notification({ id: 'n-30', title: 'Row 30' }),
    ]);
    fireEvent.click(screen.getByRole('button', { name: /load older/i }));

    expect(await screen.findByText('Row 30')).toBeInTheDocument();
    expect(screen.getAllByText('Row 29')).toHaveLength(1);
  });

  it('asks for the next page by page number, not by rendered row count', async () => {
    const firstPage = Array.from({ length: 30 }, (_, i) =>
      notification({ id: `n-${i}`, title: `Row ${i}` })
    );
    mockGetNotifications.mockResolvedValueOnce(firstPage);
    render(<NotificationsDrawer open onClose={jest.fn()} />);
    await screen.findByText('Row 0');

    // Reading a row locally must not move the offset: with the unread filter
    // on that would step straight past rows it never showed.
    fireEvent.click(screen.getByText('Row 0'));
    mockGetNotifications.mockResolvedValueOnce([]);
    fireEvent.click(screen.getByRole('button', { name: /load older/i }));

    await waitFor(() =>
      expect(mockGetNotifications).toHaveBeenLastCalledWith(
        expect.objectContaining({ skip: 30 })
      )
    );
  });
});
