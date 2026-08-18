import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NavItem } from '../NavItem';
import { type NavigationPageItem } from '@/types/navigation';
import { NotificationSection } from '@/constants/notifications';

jest.mock('@/contexts/PermissionsContext', () => ({
  useAmbientPermissions: () => ({
    permitted_actions: [],
    loading: false,
    error: null,
    enabled: false, // RBAC off -- every item permitted, matching NavSection.test.tsx's pattern
  }),
}));

const mockUnreadBySection: Record<string, number> = {};

jest.mock('@/contexts/NotificationsContext', () => ({
  useNotifications: () => ({
    unreadBySection: mockUnreadBySection,
    highlightedIds: () => [],
    markSectionRead: jest.fn(),
    clearHighlight: jest.fn(),
  }),
}));

function testSetsItem(): NavigationPageItem {
  return {
    kind: 'page',
    segment: NotificationSection.TEST_SETS,
    title: 'Test Sets',
    icon: <svg data-testid="icon" />,
  };
}

describe('NavItem notification badge', () => {
  beforeEach(() => {
    Object.keys(mockUnreadBySection).forEach(
      key => delete mockUnreadBySection[key]
    );
  });

  it('shows no badge when there are no unread notifications', () => {
    render(<NavItem item={testSetsItem()} collapsed={false} />);
    expect(screen.queryByText('1')).not.toBeInTheDocument();
  });

  it('shows the unread count next to the title when expanded', () => {
    mockUnreadBySection[NotificationSection.TEST_SETS] = 3;
    render(<NavItem item={testSetsItem()} collapsed={false} />);
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Test Sets')).toBeInTheDocument();
  });

  it('caps the displayed count at 99+', () => {
    mockUnreadBySection[NotificationSection.TEST_SETS] = 150;
    render(<NavItem item={testSetsItem()} collapsed={false} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('does not badge a segment with no matching NotificationSection', () => {
    mockUnreadBySection[NotificationSection.TEST_SETS] = 5;
    const item: NavigationPageItem = {
      kind: 'page',
      segment: 'playground',
      title: 'Playground',
    };
    render(<NavItem item={item} collapsed={false} />);
    expect(screen.queryByText('5')).not.toBeInTheDocument();
  });

  it('renders a Badge around the icon when collapsed with unread notifications', () => {
    mockUnreadBySection[NotificationSection.TEST_SETS] = 2;
    render(<NavItem item={testSetsItem()} collapsed={true} />);
    // MUI Badge renders the count in a span with class MuiBadge-badge.
    expect(document.querySelector('.MuiBadge-badge')).toHaveTextContent('2');
  });
});
