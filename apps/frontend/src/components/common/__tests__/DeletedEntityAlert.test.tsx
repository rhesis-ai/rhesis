import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeletedEntityAlert } from '../DeletedEntityAlert';
import { RecycleClient } from '@/utils/api-client/recycle-client';

jest.mock('@/utils/api-client/recycle-client', () => ({
  RecycleClient: jest.fn().mockImplementation(() => ({
    restoreItem: jest.fn().mockResolvedValue({}),
  })),
}));

const MockedRecycleClient = RecycleClient as jest.MockedClass<
  typeof RecycleClient
>;

const defaultEntityData = {
  model_name: 'TestRun',
  model_name_display: 'Test Run',
  item_name: 'My Test Run',
  item_id: 'run-123',
  table_name: 'test_run',
  restore_url: '/test-runs/run-123',
  message: 'This Test Run has been deleted.',
};

describe('DeletedEntityAlert', () => {
  it('renders the entity message', () => {
    render(<DeletedEntityAlert entityData={defaultEntityData} />);
    expect(
      screen.getByText('This Test Run has been deleted.')
    ).toBeInTheDocument();
  });

  it('shows the Restore button when sessionToken is provided', () => {
    render(
      <DeletedEntityAlert
        entityData={defaultEntityData}
        sessionToken="mock-token"
      />
    );
    expect(
      screen.getByRole('button', { name: /restore/i })
    ).toBeInTheDocument();
  });

  it('hides the Restore button when sessionToken is not provided', () => {
    render(<DeletedEntityAlert entityData={defaultEntityData} />);
    expect(
      screen.queryByRole('button', { name: /restore/i })
    ).not.toBeInTheDocument();
  });

  it('shows the Back button with custom label when backUrl and backLabel are provided', () => {
    render(
      <DeletedEntityAlert
        entityData={defaultEntityData}
        backUrl="/test-runs"
        backLabel="Back to Test Runs"
      />
    );
    expect(screen.getByText('Back to Test Runs')).toBeInTheDocument();
  });

  it('shows default "Back" label when only backUrl is provided', () => {
    render(
      <DeletedEntityAlert entityData={defaultEntityData} backUrl="/test-runs" />
    );
    expect(screen.getByText('Back')).toBeInTheDocument();
  });

  it('hides the Back button when backUrl is not provided', () => {
    render(<DeletedEntityAlert entityData={defaultEntityData} />);
    expect(screen.queryByText('Back')).not.toBeInTheDocument();
  });

  it('calls onRestoreSuccess and shows restored state after successful restore', async () => {
    const user = userEvent.setup();
    const onRestoreSuccess = jest.fn();

    render(
      <DeletedEntityAlert
        entityData={defaultEntityData}
        sessionToken="mock-token"
        onRestoreSuccess={onRestoreSuccess}
      />
    );

    await user.click(screen.getByRole('button', { name: /restore/i }));

    await waitFor(() => {
      expect(onRestoreSuccess).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText(/restored/i)).toBeInTheDocument();
  });

  it('shows an error message when restore fails', async () => {
    MockedRecycleClient.mockImplementation(
      () =>
        ({
          restoreItem: jest
            .fn()
            .mockRejectedValue(new Error('Restore failed: permission denied')),
        }) as unknown as RecycleClient
    );

    const user = userEvent.setup();

    render(
      <DeletedEntityAlert
        entityData={defaultEntityData}
        sessionToken="mock-token"
      />
    );

    await user.click(screen.getByRole('button', { name: /restore/i }));

    await waitFor(() => {
      expect(screen.getByText(/restore failed/i)).toBeInTheDocument();
    });
  });
});
