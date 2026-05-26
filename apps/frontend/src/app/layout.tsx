import * as React from 'react';
import { Metadata } from 'next';
import ThemeAwareLogo from '../components/common/ThemeAwareLogo';
import '../styles/fonts.css';
// Side-effect import: registers EE features into core's extension
// registries at module load. The actual @rhesis/ee-frontend import is
// contained in ee_bootstrap.ts (the only file allowed to do so). This
// pulls EE registrations into the server bundle; the same module is also
// pulled into the client bundle via consumers like the organization
// settings page, so registry state is populated wherever it is read.
import '../ee_bootstrap';
import ModelContextProtocolIcon from '@/components/ModelContextProtocolIcon';
import {
  ScienceIcon,
  BiotechIcon,
  AppsIcon,
  VpnKeyIcon,
  TestRunsIcon,
  AssessmentIcon,
  CategoryIcon,
  AutoGraphIcon,
  SmartToyIcon,
  EndpointsIcon,
  TasksIcon,
  KnowledgeIcon,
  BehaviorsIcon,
  KidStarIcon,
  ForumIcon,
  TracesIcon,
  PlaygroundIcon,
  AccountTreeIcon,
  EngineeringIcon,
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
): Promise<{ items: NavigationItem[]; organizationName: string }> {
  'use server';

  // Default organization name if no org found
  let organizationName = 'Rhesis AI';

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

  const navItems = [
    {
      kind: 'page',
      segment: 'architect',
      title: 'Architect',
      icon: <EngineeringIcon key="architect-icon" />,
    },
    // DEFINE section — core definition items
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
      icon: <KnowledgeIcon key="knowledge-icon" />,
    },
    {
      kind: 'page',
      segment: 'behaviors',
      title: 'Behaviors',
      icon: <BehaviorsIcon key="behaviors-icon" />,
    },
    {
      kind: 'page',
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon key="metrics-icon" />,
      requireSuperuser: true,
    },
    // GENERATE section — creation and exploration tools
    {
      kind: 'header',
      title: 'Generate',
    },
    {
      kind: 'page',
      segment: 'playground',
      title: 'Playground',
      icon: <PlaygroundIcon key="playground-icon" />,
    },
    {
      kind: 'page',
      segment: 'explorer',
      title: 'Explorer',
      icon: <AccountTreeIcon key="explorer-icon" />,
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
    // IMPROVE section — analysis and iteration
    {
      kind: 'header',
      title: 'Improve',
    },
    {
      kind: 'page',
      segment: 'insights',
      title: 'Insights',
      icon: <AssessmentIcon key="insights-icon" />,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <TestRunsIcon key="test-runs-icon" />,
    },
    {
      kind: 'page',
      segment: 'experiments',
      title: 'Experiments',
      icon: <BiotechIcon key="experiments-icon" />,
    },
    {
      kind: 'page',
      segment: 'traces',
      title: 'Traces',
      icon: <TracesIcon key="traces-icon" />,
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <TasksIcon key="tasks-icon" />,
    },
    // CONNECT section — tools and infrastructure (collapsible, collapsed by default)
    {
      kind: 'header',
      title: 'CONNECT',
      collapsible: true,
      defaultCollapsed: true,
    },
    {
      kind: 'page',
      segment: 'endpoints',
      title: 'Endpoints',
      icon: <EndpointsIcon key="endpoints-icon" />,
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
      icon: <ModelContextProtocolIcon key="mcp-icon" />,
      requireSuperuser: true,
    },
    {
      kind: 'page',
      segment: 'tokens',
      title: 'API',
      icon: <VpnKeyIcon key="tokens-icon" />,
    },
    // Divider before footer links
    {
      kind: 'divider',
    },
    // Footer external links (rendered as a white card in the sidebar)
    {
      kind: 'link',
      title: 'Star Rhesis',
      href: 'https://github.com/rhesis-ai/rhesis',
      icon: <KidStarIcon key="star-icon" />,
      external: true,
    },
    {
      kind: 'link',
      title: 'Support',
      href: 'https://github.com/rhesis-ai/rhesis/discussions',
      icon: <ForumIcon key="support-icon" />,
      external: true,
    },
  ];

  return { items: navItems as NavigationItem[], organizationName };
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

const AUTHENTICATION: AuthenticationProps = {
  signIn: handleSignIn,
  signOut: handleSignOut,
};

export default async function RootLayout(props: { children: React.ReactNode }) {
  const session = await auth().catch(() => null);

  // Get navigation with dynamic organization name
  const { items: navigation, organizationName } =
    await getNavigationItems(session);

  const branding: BrandingProps = {
    title: organizationName,
    logo: <ThemeAwareLogo />,
    homeUrl: '/architect',
  };

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
            branding={branding}
            authentication={AUTHENTICATION}
          >
            {props.children}
          </LayoutContent>
        </ThemeContextProvider>
      </body>
    </html>
  );
}
