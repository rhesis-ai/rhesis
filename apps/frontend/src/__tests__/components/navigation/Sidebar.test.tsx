import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── module mocks (must be declared before importing the component) ─────────
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(() => '/dashboard'),
}));

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

jest.mock('@/contexts/NavigationItemsContext', () => ({
  useNavigationItems: jest.fn(),
}));

jest.mock('@/components/layout/AppShell', () => ({
  useSidebarCollapse: jest.fn(() => ({ collapsed: false, toggle: jest.fn() })),
}));

jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: () => <div data-testid="user-avatar" />,
}));

jest.mock('@/components/common/ThemeAwareLogo', () => ({
  __esModule: true,
  default: () => <div data-testid="theme-logo" />,
}));

// ── imports (after mocks) ──────────────────────────────────────────────────
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import { Sidebar } from '@/components/navigation/Sidebar';
import type { NavigationItem } from '@/types/navigation';

// ── helper ────────────────────────────────────────────────────────────────
function setupMocks({
  navigation = [] as NavigationItem[],
  isSuperuser = false,
  pathname = '/dashboard',
} = {}) {
  (usePathname as jest.Mock).mockReturnValue(pathname);
  (useSession as jest.Mock).mockReturnValue({
    data: {
      user: {
        name: 'Test User',
        email: 'test@example.com',
        is_superuser: isSuperuser,
      },
    },
  });
  (useNavigationItems as jest.Mock).mockReturnValue({
    navigation,
    branding: null,
  });
  (useSidebarCollapse as jest.Mock).mockReturnValue({
    collapsed: false,
    toggle: jest.fn(),
  });
}

// ── tests ─────────────────────────────────────────────────────────────────
describe('Sidebar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', () => {
    setupMocks();
    const { container } = render(<Sidebar />);
    expect(container).toBeInTheDocument();
  });

  it('renders nav items from navigation context', () => {
    const navigation: NavigationItem[] = [
      { kind: 'page', segment: 'dashboard', title: 'Dashboard' },
      { kind: 'page', segment: 'tests', title: 'Tests' },
    ];
    setupMocks({ navigation });
    render(<Sidebar />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tests')).toBeInTheDocument();
  });

  // ── Fix 3 regression: requireSuperuser filtering ───────────────────────
  describe('requireSuperuser filtering', () => {
    const navigation: NavigationItem[] = [
      { kind: 'page', segment: 'dashboard', title: 'Dashboard' },
      {
        kind: 'page',
        segment: 'metrics',
        title: 'Metrics',
        requireSuperuser: true,
      },
      {
        kind: 'page',
        segment: 'models',
        title: 'Models',
        requireSuperuser: true,
      },
    ];

    it('hides requireSuperuser items for non-superusers', () => {
      setupMocks({ navigation, isSuperuser: false });
      render(<Sidebar />);
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.queryByText('Metrics')).not.toBeInTheDocument();
      expect(screen.queryByText('Models')).not.toBeInTheDocument();
    });

    it('shows requireSuperuser items for superusers', () => {
      setupMocks({ navigation, isSuperuser: true });
      render(<Sidebar />);
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Metrics')).toBeInTheDocument();
      expect(screen.getByText('Models')).toBeInTheDocument();
    });
  });

  // ── Fix 1 regression: full path accumulation ───────────────────────────
  describe('path accumulation for nested nav items', () => {
    it('renders child items with the correct accumulated href', () => {
      const navigation: NavigationItem[] = [
        {
          kind: 'page',
          segment: 'organizations',
          title: 'Organization',
          children: [
            { kind: 'page', segment: 'settings', title: 'Settings' },
            { kind: 'page', segment: 'team', title: 'Team' },
          ],
        },
      ];
      // Set pathname to something that makes the parent expand (active)
      setupMocks({ navigation, pathname: '/organizations/settings' });
      render(<Sidebar />);

      // The child link must have the full path, not just /settings
      const settingsLink = screen.getByRole('link', { name: /settings/i });
      expect(settingsLink).toHaveAttribute('href', '/organizations/settings');
    });

    it('renders a top-level item with the correct href', () => {
      const navigation: NavigationItem[] = [
        { kind: 'page', segment: 'tests', title: 'Tests' },
      ];
      setupMocks({ navigation });
      render(<Sidebar />);

      const testsLink = screen.getByRole('link', { name: /tests/i });
      expect(testsLink).toHaveAttribute('href', '/tests');
    });
  });

  it('renders the user name when session is available', () => {
    setupMocks({ navigation: [] });
    render(<Sidebar />);
    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  it('falls back to "User" when session has no name', () => {
    (usePathname as jest.Mock).mockReturnValue('/dashboard');
    (useSession as jest.Mock).mockReturnValue({
      data: { user: { email: 'test@example.com' } },
    });
    (useNavigationItems as jest.Mock).mockReturnValue({
      navigation: [],
      branding: null,
    });
    (useSidebarCollapse as jest.Mock).mockReturnValue({
      collapsed: false,
      toggle: jest.fn(),
    });
    render(<Sidebar />);
    expect(screen.getByText('User')).toBeInTheDocument();
  });
});
