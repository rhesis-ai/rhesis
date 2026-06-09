import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockRouterPush = jest.fn();

// ── module mocks (must be declared before importing the component) ─────────
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(() => '/insights'),
  useRouter: jest.fn(() => ({ push: mockRouterPush })),
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

jest.mock('@/actions/auth', () => ({
  handleSignOut: jest.fn(),
}));

jest.mock('@/components/providers/ThemeProvider', () => ({
  ColorModeContext: React.createContext({
    toggleColorMode: jest.fn(),
    mode: 'light',
  }),
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
  pathname = '/insights',
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
    mockRouterPush.mockClear();
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
      { kind: 'page', segment: 'insights', title: 'Insights' },
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
      expect(screen.getByText('Insights')).toBeInTheDocument();
      expect(screen.queryByText('Metrics')).not.toBeInTheDocument();
      expect(screen.queryByText('Models')).not.toBeInTheDocument();
    });

    it('shows requireSuperuser items for superusers', () => {
      setupMocks({ navigation, isSuperuser: true });
      render(<Sidebar />);
      expect(screen.getByText('Insights')).toBeInTheDocument();
      expect(screen.getByText('Metrics')).toBeInTheDocument();
      expect(screen.getByText('Models')).toBeInTheDocument();
    });
  });

  // ── Fix 1 regression: full path accumulation ───────────────────────────
  describe('path accumulation for nested nav items', () => {
    it('renders a parent nav item at its segment path (children are not inline)', () => {
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
      setupMocks({ navigation, pathname: '/organizations/settings' });
      render(<Sidebar />);

      const orgLink = screen.getByRole('link', { name: /organization/i });
      expect(orgLink).toHaveAttribute('href', '/organizations');
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

  describe('org menu popover', () => {
    it('does not link the brand row directly to /organizations', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      const orgLinks = screen
        .queryAllByRole('link')
        .filter(link => link.getAttribute('href') === '/organizations');
      expect(orgLinks).toHaveLength(0);
    });

    it('opens Settings and Team in a popover when the org brand is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Team')).toBeInTheDocument();
    });

    it('navigates to settings when Settings is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      fireEvent.click(screen.getByText('Settings'));
      expect(mockRouterPush).toHaveBeenCalledWith('/organizations/settings');
    });

    it('navigates to team when Team is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      fireEvent.click(screen.getByText('Team'));
      expect(mockRouterPush).toHaveBeenCalledWith('/organizations/team');
    });
  });

  it('falls back to "User" when session has no name', () => {
    (usePathname as jest.Mock).mockReturnValue('/insights');
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
