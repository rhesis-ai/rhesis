import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import BaseWorkflowSection from '../BaseWorkflowSection';

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsersClient: () => ({
      getUsers: jest.fn().mockResolvedValue({ data: [] }),
    }),
    getStatusClient: () => ({
      getStatuses: jest.fn().mockResolvedValue([]),
    }),
  })),
}));

const onUpdateEntity = jest.fn().mockResolvedValue(undefined);

function renderSection(
  props: Partial<React.ComponentProps<typeof BaseWorkflowSection>> = {}
) {
  return render(
    <BaseWorkflowSection
      entityId="e1"
      entityType="Test"
      onUpdateEntity={onUpdateEntity}
      {...props}
    />
  );
}

describe('BaseWorkflowSection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', () => {
    renderSection();
    expect(document.body).toBeInTheDocument();
  });

  it('renders the section title when provided', () => {
    renderSection({ title: 'Workflow' });
    expect(screen.getByText('Workflow')).toBeInTheDocument();
  });

  it('renders Status and Priority autocompletes', () => {
    renderSection();
    expect(
      screen.getByRole('combobox', { name: /status/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: /priority/i })
    ).toBeInTheDocument();
  });

  it('renders the status value when provided via preloadedStatuses', async () => {
    renderSection({
      preloadedStatuses: [
        {
          id: 's1',
          name: 'Open',
          description: 'open',
          entity_type: 'Test',
        } as never,
      ],
      status: 'Open',
    });

    await waitFor(() => {
      const statusInput = screen.getByRole('combobox', { name: /status/i });
      expect((statusInput as HTMLInputElement).value).toBe('Open');
    });
  });

  it('renders the assignee once users are loaded from preloadedUsers', async () => {
    renderSection({
      preloadedUsers: [
        {
          id: 'u1',
          name: 'Alice',
          email: 'alice@test.com',
          is_active: true,
        } as never,
      ],
      assignee: { id: 'u1', name: 'Alice' } as never,
    });

    // Once the users effect runs, the assignee autocomplete value should be Alice
    await waitFor(() => {
      const assigneeInput = screen.getByRole('combobox', { name: /assignee/i });
      expect((assigneeInput as HTMLInputElement).value).toBe('Alice');
    });
  });

  it('renders in read-only status mode when statusReadOnly=true', async () => {
    renderSection({
      statusReadOnly: true,
      status: 'Completed',
      preloadedStatuses: [
        {
          id: 's2',
          name: 'Completed',
          description: '',
          entity_type: 'Test',
        } as never,
      ],
    });

    await waitFor(() => {
      const statusInput = screen.getByRole('combobox', { name: /status/i });
      expect((statusInput as HTMLInputElement).value).toBe('Completed');
    });
  });

  it('hides priority when showPriority=false', () => {
    renderSection({ showPriority: false });
    expect(
      screen.queryByRole('combobox', { name: /priority/i })
    ).not.toBeInTheDocument();
  });
});
