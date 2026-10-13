import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ProjectAddMemberDrawer from '../ProjectAddMemberDrawer';

const mockUseUsers = jest.fn();

jest.mock('@/hooks/useLookups', () => ({
  useUsers: (enabled: boolean) => mockUseUsers(enabled),
}));

jest.mock('@/components/common/BaseDrawer', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/contexts/FeaturesContext', () => ({
  useFeature: () => false,
}));

jest.mock('@/lib/extension-registries', () => ({
  getMemberRoleExtensions: () => ({}),
}));

const USERS = Array.from({ length: 150 }, (_, i) => ({
  id: `u${i}`,
  name: `User ${i}`,
  email: `user${i}@example.com`,
}));

function renderDrawer(memberUserIds: string[] = []) {
  return render(
    <ProjectAddMemberDrawer
      open
      onClose={jest.fn()}
      projectId="p1"
      memberUserIds={memberUserIds}
      onMemberAdded={jest.fn()}
    />
  );
}

function openOptions() {
  fireEvent.mouseDown(screen.getByLabelText('Organisation member'));
}

describe('ProjectAddMemberDrawer', () => {
  beforeEach(() => {
    mockUseUsers.mockReset();
    mockUseUsers.mockReturnValue({
      data: USERS,
      isLoading: false,
      isError: false,
    });
  });

  it('offers users past the first 100, minus existing members', () => {
    renderDrawer(['u0']);
    openOptions();

    expect(mockUseUsers).toHaveBeenCalledWith(true);
    expect(screen.getByText('User 149')).toBeInTheDocument();
    expect(screen.queryByText('User 0')).not.toBeInTheDocument();
  });

  it('shows a warning when users fail to load', () => {
    mockUseUsers.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    renderDrawer();

    expect(
      screen.getByText('Failed to load organisation members.')
    ).toBeInTheDocument();
  });
});
