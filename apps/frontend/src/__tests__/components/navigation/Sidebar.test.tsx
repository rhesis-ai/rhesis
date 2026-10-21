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

const mockUnreadBySection: { current: Record<string, number> } = {
  current: {},
};
jest.mock('@/contexts/NotificationsContext', () => ({
  useNotifications: () => ({
    unreadBySection: mockUnreadBySection.current,
    markSectionRead: jest.fn(),
    markOneRead: jest.fn(),
    highlightedIds: () => [],
    clearHighlight: jest.fn(),
    registerViewing: () => () => {},
  }),
}));

jest.mock('@/components/common/ThemeAwareLogo', () => ({
  __esModule: true,
  default: () => <div data-testid="theme-logo" />,
}));

jest.mock('@/actions/auth', () => ({
  handleSignOut: jest.fn(),
}));

const mockToggleColorMode = jest.fn();
jest.mock('@/components/providers/ThemeProvider', () => ({
  ColorModeContext: React.createContext({
    toggleColorMode: () => mockToggleColorMode(),
    mode: 'light',
  }),
}));

const mockActiveProject: {
  current: { id: string; name: string } | null;
} = { current: null };
jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({
    projects: mockActiveProject.current ? [mockActiveProject.current] : [],
    activeProject: mockActiveProject.current,
    loading: false,
    setActiveProject: jest.fn(),
  }),
}));

const mockCanCreate = { current: true };
jest.mock('@/components/common/Can', () => ({
  useCan: () => mockCanCreate.current,
  useCanWithStatus: () => ({ allowed: mockCanCreate.current, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) =>
    mockCanCreate.current ? <>{children}</> : null,
  can: () => mockCanCreate.current,
}));

const mockUsageResources: {
  current: Record<
    string,
    {
      used: number;
      limit: number | null;
      ceiling: number | null;
      kind: 'stock' | 'flow';
      period_start: string;
      period_end: string;
    }
  >;
} = { current: {} };
const mockUsagePlan: {
  current: { name: string; is_paid: boolean; is_active: boolean } | null;
} = { current: { name: 'Community', is_paid: false, is_active: false } };
jest.mock('@/contexts/UsageContext', () => ({
  useUsage: () => ({
    resources: mockUsageResources.current,
    edition: 'community',
    loading: false,
    error: null,
  }),
}));

// Only `usePlan` is stubbed -- spreading the real module keeps `useFeature`
// and friends intact for the rest of the tree. The plan rides on
// `GET /features` because that response is server-seeded, so the row has it on
// first paint.
jest.mock('@/contexts/FeaturesContext', () => ({
  ...jest.requireActual('@/contexts/FeaturesContext'),
  usePlan: () => mockUsagePlan.current,
}));

// Covered in its own test; it needs the OnboardingProvider this tree lacks.
jest.mock('@/components/navigation/SidebarOnboardingRow', () => ({
  SidebarOnboardingRow: () => null,
}));

// ── imports (after mocks) ──────────────────────────────────────────────────
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { useSidebarCollapse } from '@/components/layout/AppShell';
import { Sidebar } from '@/components/navigation/Sidebar';
import type { NavigationItem } from '@/types/navigation';
import { QuotaResource } from '@/constants/quota';

// ── helper ────────────────────────────────────────────────────────────────
function setupMocks({
  navigation = [] as NavigationItem[],
  pathname = '/insights',
} = {}) {
  (usePathname as jest.Mock).mockReturnValue(pathname);
  (useSession as jest.Mock).mockReturnValue({
    data: {
      user: {
        name: 'Test User',
        email: 'test@example.com',
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
    mockUnreadBySection.current = {};
    mockUsageResources.current = {};
    mockActiveProject.current = null;
    mockCanCreate.current = true;
    mockUsagePlan.current = {
      name: 'Community',
      is_paid: false,
      is_active: false,
    };
  });

  describe('plan row in the footer card', () => {
    /** The footer card the plan row heads, keyed off a link it always has. */
    function footerCard(container: HTMLElement): HTMLElement {
      const starLink = screen.getByText('Star Rhesis');
      const card = starLink.closest('div')?.parentElement;
      if (!card) throw new Error('footer card not found');
      expect(container).toContainElement(card);
      return card;
    }

    const footerNav: NavigationItem[] = [
      { kind: 'divider' },
      {
        kind: 'link',
        title: 'Star Rhesis',
        href: 'https://github.com/rhesis-ai/rhesis',
        external: true,
      },
      { kind: 'action', title: 'Support', action: 'support' },
    ];

    it('sits above Star Rhesis', () => {
      setupMocks({ navigation: footerNav });
      const { container } = render(<Sidebar />);

      const card = footerCard(container);
      const plan = screen.getByText('Community');
      const star = screen.getByText('Star Rhesis');

      expect(card).toContainElement(plan);
      // Ordered comparison rather than an index: DOCUMENT_POSITION_FOLLOWING
      // says "star comes after plan" without depending on the card's exact
      // nesting, which the styling wrappers can change.
      expect(
        plan.compareDocumentPosition(star) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
    });

    it('names an active paid plan', () => {
      mockUsagePlan.current = {
        name: 'Enterprise',
        is_paid: true,
        is_active: true,
      };
      setupMocks({ navigation: footerNav });
      render(<Sidebar />);

      expect(screen.getByText('Enterprise')).toBeInTheDocument();
    });

    it('marks a lapsed paid plan inactive', () => {
      mockUsagePlan.current = {
        name: 'Enterprise (inactive)',
        is_paid: true,
        is_active: false,
      };
      setupMocks({ navigation: footerNav });
      render(<Sidebar />);

      expect(screen.getByText('Enterprise (inactive)')).toBeInTheDocument();
    });
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

  it('shows all nav items regardless of user role', () => {
    const navigation: NavigationItem[] = [
      { kind: 'page', segment: 'insights', title: 'Insights' },
      { kind: 'page', segment: 'metrics', title: 'Metrics' },
      { kind: 'page', segment: 'models', title: 'Models' },
    ];
    setupMocks({ navigation });
    render(<Sidebar />);
    expect(screen.getByText('Insights')).toBeInTheDocument();
    expect(screen.getByText('Metrics')).toBeInTheDocument();
    expect(screen.getByText('Models')).toBeInTheDocument();
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

    it('opens org menu items in a popover when the org brand is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      expect(screen.getByText('Org Settings')).toBeInTheDocument();
      expect(screen.queryByText('Team')).not.toBeInTheDocument();
      expect(screen.getByText('Projects')).toBeInTheDocument();
      // Switching lives in the project box now, not the org menu.
      expect(
        screen.queryByRole('menuitem', { name: /switch project/i })
      ).not.toBeInTheDocument();
    });

    it('fills a usage row bar to how much of the limit is used', () => {
      mockUsageResources.current = {
        [QuotaResource.PROJECTS]: {
          used: 1,
          limit: 1,
          ceiling: 1,
          kind: 'stock',
          period_start: '2026-08-01',
          period_end: '2026-08-31',
        },
      };
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));

      expect(screen.getByText('1 of 1')).toBeInTheDocument();
      const fill = screen.getByTestId('usage-row-fill');
      expect(getComputedStyle(fill).width).toBe('100%');
    });

    it('navigates to org settings when Org Settings is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      fireEvent.click(screen.getByText('Org Settings'));
      expect(mockRouterPush).toHaveBeenCalledWith('/organizations/settings');
    });

    it('navigates to projects when Projects is clicked', () => {
      setupMocks();
      (useNavigationItems as jest.Mock).mockReturnValue({
        navigation: [],
        branding: { title: 'Acme Corp', logo: null, homeUrl: '/architect' },
      });
      render(<Sidebar />);
      fireEvent.click(screen.getByText('Acme Corp'));
      fireEvent.click(screen.getByText('Projects'));
      expect(mockRouterPush).toHaveBeenCalledWith('/projects');
    });
  });

  describe('project box', () => {
    it('shows the active project, not in the org header', () => {
      mockActiveProject.current = { id: 'p1', name: 'Insurance Chatbot' };
      setupMocks();
      render(<Sidebar />);
      const box = screen.getByRole('button', {
        name: 'Switch project, current: Insurance Chatbot',
      });
      expect(box).toHaveTextContent('Insurance Chatbot');
      expect(screen.getAllByText('Insurance Chatbot')).toHaveLength(1);
    });

    it('opens project settings for the active project', () => {
      mockActiveProject.current = { id: 'p1', name: 'Insurance Chatbot' };
      setupMocks();
      render(<Sidebar />);
      fireEvent.click(
        screen.getByRole('button', { name: /switch project, current/i })
      );
      fireEvent.click(screen.getByText('Project Settings'));
      expect(mockRouterPush).toHaveBeenCalledWith('/projects/p1');
    });

    it('links to the org-level overview and the create page', () => {
      mockActiveProject.current = { id: 'p1', name: 'Insurance Chatbot' };
      setupMocks();
      render(<Sidebar />);
      fireEvent.click(
        screen.getByRole('button', { name: /switch project, current/i })
      );
      fireEvent.click(screen.getByText('All Projects'));
      expect(mockRouterPush).toHaveBeenCalledWith('/projects');

      fireEvent.click(
        screen.getByRole('button', { name: /switch project, current/i })
      );
      fireEvent.click(screen.getByText('New Project'));
      expect(mockRouterPush).toHaveBeenCalledWith('/projects/create-new');
    });

    it('hides New project without the create capability', () => {
      mockActiveProject.current = { id: 'p1', name: 'Insurance Chatbot' };
      mockCanCreate.current = false;
      setupMocks();
      render(<Sidebar />);
      fireEvent.click(
        screen.getByRole('button', { name: /switch project, current/i })
      );
      expect(screen.getByText('All Projects')).toBeInTheDocument();
      expect(screen.queryByText('New Project')).not.toBeInTheDocument();
    });

    it('asks to select a project when none is active', () => {
      setupMocks();
      render(<Sidebar />);
      fireEvent.click(screen.getByRole('button', { name: 'Select a project' }));
      expect(screen.queryByText('Project Settings')).not.toBeInTheDocument();
      expect(screen.getByText('No projects found.')).toBeInTheDocument();
    });
  });

  describe('dark mode', () => {
    it('toggles from the user menu', () => {
      setupMocks();
      render(<Sidebar />);
      fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
      fireEvent.click(screen.getByRole('menuitem', { name: 'Dark Mode' }));
      expect(mockToggleColorMode).toHaveBeenCalledTimes(1);
    });

    it('is not in the footer card', () => {
      setupMocks();
      render(<Sidebar />);
      expect(
        screen.queryByRole('button', { name: /dark mode/i })
      ).not.toBeInTheDocument();
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

  it('badges the avatar with the total unread count, so notifications are visible without opening the menu', () => {
    mockUnreadBySection.current = { 'test-runs': 2, usage: 1 };
    setupMocks();
    render(<Sidebar />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('does not badge the avatar when nothing is unread', () => {
    setupMocks();
    render(<Sidebar />);
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});
