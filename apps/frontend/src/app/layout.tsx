import * as React from 'react';
import { Metadata } from 'next';
import ThemeAwareLogo from '../components/common/ThemeAwareLogo';
import '../styles/fonts.css';
import {
  DashboardIcon,
  ScienceIcon,
  AppsIcon,
  VpnKeyIcon,
  BusinessIcon,
  GroupIcon,
  CategoryIcon,
  SmartToyIcon,
  TerminalIcon,
  SettingsIcon,
  MenuBookIcon,
  BoltIcon,
  PsychologyIcon,
  AccountTreeIcon,
  RouteIcon,
  FingerprintIcon,
  BarChartIcon,
  SlideshowIcon,
  ChecklistRtlIcon,
  SportsFootballIcon,
  ShowChartIcon,
  InsertChartIcon,
} from '@/components/icons';
import { auth } from '../auth';
import { handleSignIn, handleSignOut } from '../actions/auth';
import { LayoutContent } from '../components/layout/LayoutContent';
import { ApiClientFactory } from '../utils/api-client/client-factory';
import {
  type NavigationItem,
  type BrandingProps,
  type AuthenticationProps,
} from '../types/navigation';
import { type Session } from 'next-auth';
import ThemeContextProvider from '../components/providers/ThemeProvider';

// Mark this layout as dynamic since it uses server-side authentication
export const dynamic = 'force-dynamic';

// This function will be used to get navigation items with dynamic data
async function getNavigationItems(
  session: Session | null
): Promise<NavigationItem[]> {
  'use server';

  // Default organization name if no org found
  let organizationName = 'Organization';

  // Fetch organization name if user has an organization_id
  if (session?.user?.organization_id && session?.session_token) {
    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const organizationsClient = clientFactory.getOrganizationsClient();
      const organization = await organizationsClient.getOrganization(
        session.user.organization_id
      );
      if (organization?.name) {
        organizationName = organization.name;
      }
    } catch (error) {
      // If this is an Unauthorized error (expired JWT), the session is invalid
      // Log it but continue with default navigation to allow the client-side
      // session handling to take over
      if (error instanceof Error && error.message.includes('Unauthorized')) {
      }
      // Continue with default organization name
    }
  }

  return [
    // Organization (hidden from sidebar, accessed via CompanyMenu popover)
    {
      kind: 'page',
      segment: 'organizations',
      title: organizationName,
      icon: <BusinessIcon key="org-icon" />,
      children: [
        {
          kind: 'page',
          segment: 'settings',
          title: 'Settings',
          icon: <SettingsIcon key="settings-icon" />,
        },
        {
          kind: 'page',
          segment: 'team',
          title: 'Team',
          icon: <GroupIcon key="team-icon" />,
        },
      ],
    },
    // Dashboard — standalone, above categories
    {
      kind: 'page',
      segment: 'dashboard',
      title: 'Dashboard',
      icon: <DashboardIcon key="dashboard-icon" />,
    },
    // DEFINE
    {
      kind: 'header',
      title: 'Define',
    },
    {
      kind: 'page',
      segment: 'projects',
      title: 'Projects',
      icon: <AppsIcon key="projects-icon" />,
    },
    {
      kind: 'page',
      segment: 'knowledge',
      title: 'Knowledge',
      icon: <MenuBookIcon key="knowledge-icon" />,
    },
    {
      kind: 'page',
      segment: 'behaviors',
      title: 'Behaviors',
      icon: <PsychologyIcon key="behaviors-icon" />,
    },
    {
      kind: 'page',
      segment: 'tests',
      title: 'Tests',
      icon: <ScienceIcon key="tests-icon" />,
    },
    {
      kind: 'page',
      segment: 'test-sets',
      title: 'Test Sets',
      icon: <CategoryIcon key="test-sets-icon" />,
    },
    {
      kind: 'page',
      segment: 'generation',
      title: 'Generation',
      icon: <BoltIcon key="generation-icon" />,
    },
    {
      kind: 'page',
      segment: 'playground',
      title: 'Playground',
      icon: <SportsFootballIcon key="playground-icon" />,
    },
    // EVALUATE
    {
      kind: 'header',
      title: 'Evaluate',
    },
    {
      kind: 'page',
      segment: 'test-results',
      title: 'Overview',
      icon: <InsertChartIcon key="test-results-icon" />,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <SlideshowIcon key="test-runs-icon" />,
    },
    {
      kind: 'page',
      segment: 'traces',
      title: 'Traces',
      icon: <FingerprintIcon key="traces-icon" />,
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <ChecklistRtlIcon key="tasks-icon" />,
    },
    {
      kind: 'page',
      segment: 'metrics',
      title: 'Metrics',
      icon: <ShowChartIcon key="metrics-icon" />,
      requireSuperuser: true,
    },
    ...(process.env.NODE_ENV === 'development'
      ? [
          {
            kind: 'page' as const,
            segment: 'adaptive-testing',
            title: 'Adaptive Testing',
            icon: <AccountTreeIcon key="adaptive-testing-icon" />,
          },
        ]
      : []),
    // DEVELOP
    {
      kind: 'header',
      title: 'Develop',
    },
    {
      kind: 'page',
      segment: 'endpoints',
      title: 'Endpoints',
      icon: <RouteIcon key="endpoints-icon" />,
    },
    {
      kind: 'page',
      segment: 'models',
      title: 'Models',
      icon: <SmartToyIcon key="models-icon" />,
      requireSuperuser: true,
    },
    {
      kind: 'page',
      segment: 'mcp',
      title: 'MCP',
      icon: <TerminalIcon key="mcp-icon" />,
      requireSuperuser: true,
    },
    {
      kind: 'page',
      segment: 'tokens',
      title: 'API Tokens',
      icon: <VpnKeyIcon key="tokens-icon" />,
    },
  ] as NavigationItem[];
}

export const metadata: Metadata = {
  title: {
    template: '%s | Rhesis AI',
    default: 'Rhesis AI',
  },
  description: 'Rhesis AI | OSS Gen AI Testing Platform',
  icons: {
    icon: '/logos/rhesis-logo-favicon.svg',
  },
};

const BRANDING: BrandingProps = {
  title: '',
  logo: <ThemeAwareLogo />,
  homeUrl: '/dashboard',
};

const AUTHENTICATION: AuthenticationProps = {
  signIn: handleSignIn,
  signOut: handleSignOut,
};

export default async function RootLayout(props: { children: React.ReactNode }) {
  const session = await auth().catch(() => null);

  // Get navigation with dynamic organization name
  const navigation = await getNavigationItems(session);

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var THEME_MODE_KEY = 'theme-mode';
                  var storedMode = localStorage.getItem(THEME_MODE_KEY);
                  var mode;

                  if (storedMode) {
                    mode = storedMode;
                  } else {
                    var darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
                    mode = darkModeQuery.matches ? 'dark' : 'light';
                  }

                  document.documentElement.setAttribute('data-theme-mode', mode);
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body suppressHydrationWarning>
        <ThemeContextProvider disableTransitionOnChange>
          <LayoutContent
            session={session}
            navigation={navigation}
            branding={BRANDING}
            authentication={AUTHENTICATION}
          >
            {props.children}
          </LayoutContent>
        </ThemeContextProvider>
      </body>
    </html>
  );
}
