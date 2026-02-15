import * as React from 'react';
import { Metadata } from 'next';
import { Box, Tooltip } from '@mui/material';
import ThemeAwareLogo from '../components/common/ThemeAwareLogo';
import '../styles/fonts.css';
import {
  DashboardIcon,
  ScienceIcon,
  AppsIcon,
  VpnKeyIcon,
  BusinessIcon,
  GroupIcon,
  PlayArrowIcon,
  AssessmentIcon,
  CategoryIcon,
  AutoGraphIcon,
  SmartToyIcon,
  ApiIcon,
  TerminalIcon,
  AssignmentIcon,
  SettingsIcon,
  MenuBookIcon,
  BoltIcon,
  PsychologyIcon,
  GitHubIcon,
  DescriptionIcon,
  CodeIcon,
  TimelineIcon,
  ChatIcon,
  AccountTreeIcon,
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
    // Organization Section
    {
      kind: 'page',
      segment: 'organizations',
      title: (
        <Tooltip
          placement="top"
          // sidebar is 240px, px to rem conversion => 240/16=15, so from 16 characters we display ellipsis+tooltip
          title={organizationName.length < 15 ? '' : organizationName}
        >
          <Box sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {organizationName}
          </Box>
        </Tooltip>
      ),
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
    // Dashboard
    {
      kind: 'page',
      segment: 'dashboard',
      title: 'Dashboard',
      icon: <DashboardIcon key="dashboard-icon" />,
    },
    // Requirements Section
    {
      kind: 'header',
      title: 'Requirements',
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
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon key="metrics-icon" />,
      requireSuperuser: true,
    },
    // Testing Section
    {
      kind: 'header',
      title: 'Testing',
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
      icon: <ChatIcon key="playground-icon" />,
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
    // Results Section
    {
      kind: 'header',
      title: 'Results',
    },
    {
      kind: 'page',
      segment: 'test-results',
      title: 'Overview',
      icon: <AssessmentIcon key="test-results-icon" />,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <PlayArrowIcon key="test-runs-icon" />,
    },
    {
      kind: 'page',
      segment: 'traces',
      title: 'Traces',
      icon: <TimelineIcon key="traces-icon" />,
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <AssignmentIcon key="tasks-icon" />,
    },
    // Development Section
    {
      kind: 'header',
      title: 'Development',
    },
    {
      kind: 'page',
      segment: 'endpoints',
      title: 'Endpoints',
      icon: <ApiIcon key="endpoints-icon" />,
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
    // Divider before external links
    {
      kind: 'divider',
    },
    // External Links
    {
      kind: 'link',
      title: '⭐ Star Rhesis',
      href: 'https://github.com/rhesis-ai/rhesis',
      icon: <GitHubIcon key="star-icon" className="star-rhesis-icon" />,
      external: true,
    },
    {
      kind: 'link',
      title: 'Documentation',
      href: 'https://docs.rhesis.ai',
      icon: <DescriptionIcon key="docs-icon" />,
      external: true,
    },
    {
      kind: 'link',
      title: 'SDK Reference',
      href: 'https://rtd.rhesis.ai',
      icon: <CodeIcon key="sdk-icon" />,
      external: true,
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
