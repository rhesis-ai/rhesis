import * as React from 'react';
import { Metadata } from 'next';
import Script from 'next/script';
import { cookies } from 'next/headers';
import ThemeAwareLogo from '../components/common/ThemeAwareLogo';
import '../styles/fonts.css';
// Side-effect import: registers EE features into core's extension
// registries at module load. The actual @rhesis/ee-frontend import is
// contained in ee_bootstrap.ts (the only file allowed to do so). This
// pulls EE registrations into the server bundle; the same module is also
// pulled into the client bundle via consumers like the organization
// settings page, so registry state is populated wherever it is read.
import '../ee_bootstrap';
import '../lib/org-settings-tabs-bootstrap';
import {
  ScienceIcon,
  BiotechIcon,
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
  RateReviewIcon,
  TracesIcon,
  PlaygroundIcon,
  AccountTreeIcon,
  EngineeringIcon,
  BuildIcon,
} from '@/components/icons';
import { auth } from '../auth';
import { handleSignIn, handleSignOut } from '../actions/auth';
import { LayoutContent } from '../components/layout/LayoutContent';
import { createServerApiFactory } from '../utils/api-client/server-factory';
import { getServerActiveProjectId } from '../utils/server-active-project';
import {
  type NavigationItem,
  type BrandingProps,
  type AuthenticationProps,
} from '../types/navigation';
import { type Project } from '../utils/api-client/interfaces/project';
import { type Organization } from '../utils/api-client/interfaces/organization';
import { type Session } from 'next-auth';
import ThemeContextProvider from '../components/providers/ThemeProvider';
import { Capability } from '../constants/capabilities';

// Mark this layout as dynamic since it uses server-side authentication
export const dynamic = 'force-dynamic';

// This function will be used to get navigation items with dynamic data
async function getNavigationItems(session: Session | null): Promise<{
  items: NavigationItem[];
  organizationName: string;
  organization: Organization | null;
}> {
  'use server';

  let organizationName = 'Rhesis AI';
  let organization: Organization | null = null;

  if (session?.user?.organization_id && !session.error) {
    try {
      const clientFactory = await createServerApiFactory();
      organization = await clientFactory
        .getOrganizationsClient()
        .getOrganization(session.user.organization_id);
      if (organization?.name) {
        organizationName = organization.name;
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes('Unauthorized')) {
      }
    }
  }

  const navItems = [
    {
      kind: 'page',
      segment: 'architect',
      title: 'Architect',
      icon: <EngineeringIcon key="architect-icon" />,
      requiredPermission: Capability.Architect.READ,
    },
    // DEFINE section — core definition items
    {
      kind: 'header',
      title: 'Define',
    },
    {
      kind: 'page',
      segment: 'knowledge',
      title: 'Knowledge',
      icon: <KnowledgeIcon key="knowledge-icon" />,
      requiredPermission: Capability.Source.READ,
    },
    {
      kind: 'page',
      segment: 'behaviors',
      title: 'Behaviors',
      icon: <BehaviorsIcon key="behaviors-icon" />,
      requiredPermission: Capability.Behavior.READ,
    },
    {
      kind: 'page',
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon key="metrics-icon" />,
      requiredPermission: Capability.Metric.READ,
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
      requiredPermission: Capability.Playground.USE,
    },
    {
      kind: 'page',
      segment: 'explorer',
      title: 'Explorer',
      icon: <AccountTreeIcon key="explorer-icon" />,
      requiredPermission: Capability.Explorer.READ,
    },
    {
      kind: 'page',
      segment: 'tests',
      title: 'Tests',
      icon: <ScienceIcon key="tests-icon" />,
      requiredPermission: Capability.Test.READ,
    },
    {
      kind: 'page',
      segment: 'test-sets',
      title: 'Test Sets',
      icon: <CategoryIcon key="test-sets-icon" />,
      requiredPermission: Capability.TestSet.READ,
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
      requiredPermission: Capability.TestResult.READ,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <TestRunsIcon key="test-runs-icon" />,
      requiredPermission: Capability.TestRun.READ,
    },
    {
      kind: 'page',
      segment: 'experiments',
      title: 'Experiments',
      icon: <BiotechIcon key="experiments-icon" />,
      requiredPermission: Capability.Experiment.READ,
    },
    {
      kind: 'page',
      segment: 'traces',
      title: 'Traces',
      icon: <TracesIcon key="traces-icon" />,
      requiredPermission: Capability.Telemetry.READ,
    },
    {
      kind: 'page',
      segment: 'annotations',
      title: 'Annotations',
      icon: <RateReviewIcon key="annotations-icon" />,
      requiredAnyOf: [Capability.TestResult.READ, Capability.Telemetry.READ],
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <TasksIcon key="tasks-icon" />,
      requiredPermission: Capability.Task.READ,
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
      requiredPermission: Capability.Endpoint.READ,
    },
    {
      kind: 'page',
      segment: 'models',
      title: 'Models',
      icon: <SmartToyIcon key="models-icon" />,
      requiredPermission: Capability.Model.READ,
    },
    {
      kind: 'page',
      segment: 'tools',
      title: 'Tools',
      icon: <BuildIcon key="tool-icon" />,
      requiredPermission: Capability.Tool.READ,
    },
    {
      kind: 'page',
      segment: 'tokens',
      title: 'API',
      icon: <VpnKeyIcon key="tokens-icon" />,
      requiredPermission: Capability.Token.MANAGE,
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
      kind: 'action',
      title: 'Support',
      action: 'support',
      icon: <ForumIcon key="support-icon" />,
    },
  ];

  return {
    items: navItems as NavigationItem[],
    organizationName,
    organization,
  };
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
  const themeCookie = (await cookies()).get('theme-mode')?.value;
  const initialThemeMode = themeCookie === 'dark' ? 'dark' : 'light';

  // Get navigation with dynamic organization name
  const {
    items: navigation,
    organizationName,
    organization,
  } = await getNavigationItems(session);

  const branding: BrandingProps = {
    title: organizationName,
    logo: <ThemeAwareLogo />,
    homeUrl: '/architect',
  };
  const runtimeEnvScript = `window.__ENV__=${JSON.stringify({
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8080',
  }).replace(/</g, '\\u003c')};`;

  // Fetch the active project server-side so the sidebar can render the
  // project name on first paint without a flash.
  let initialActiveProject: Project | null = null;
  const projectId = await getServerActiveProjectId();
  if (projectId && session && !session.error) {
    try {
      const factory = await createServerApiFactory();
      initialActiveProject = await factory
        .getProjectsClient()
        .getProject(projectId);
    } catch {
      // Ignore — client will fetch on mount
    }
  }

  return (
    <html lang="en" suppressHydrationWarning data-theme-mode={initialThemeMode}>
      <body suppressHydrationWarning>
        <Script id="rhesis-runtime-env" strategy="beforeInteractive">
          {runtimeEnvScript}
        </Script>
        <ThemeContextProvider
          disableTransitionOnChange
          initialMode={initialThemeMode}
        >
          <LayoutContent
            session={session}
            navigation={navigation}
            branding={branding}
            authentication={AUTHENTICATION}
            initialActiveProject={initialActiveProject}
            initialOrganization={organization}
          >
            {props.children}
          </LayoutContent>
        </ThemeContextProvider>
      </body>
    </html>
  );
}
