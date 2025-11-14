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
  IntegrationInstructionsIcon,
  SmartToyIcon,
  GridViewIcon,
  ApiIcon,
  TerminalIcon,
  AssignmentIcon,
  SettingsIcon,
  MenuBookIcon,
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
      icon: <BusinessIcon />,
      children: [
        {
          kind: 'page',
          segment: 'settings',
          title: 'Settings',
          icon: <SettingsIcon />,
        },
        {
          kind: 'page',
          segment: 'team',
          title: 'Team',
          icon: <GroupIcon />,
        },
      ],
    },
    {
      kind: 'page',
      segment: 'projects',
      title: 'Projects',
      icon: <AppsIcon />,
    },
    {
      kind: 'page',
      segment: 'knowledge',
      title: 'Knowledge',
      icon: <MenuBookIcon />,
    },
    {
      kind: 'divider',
    },
    {
      kind: 'page',
      segment: 'dashboard',
      title: 'Dashboard',
      icon: <DashboardIcon />,
    },
    {
      kind: 'page',
      segment: 'tests',
      title: 'Tests',
      icon: <ScienceIcon />,
    },
    {
      kind: 'page',
      segment: 'test-sets',
      title: 'Test Sets',
      icon: <CategoryIcon />,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <PlayArrowIcon />,
    },
    {
      kind: 'page',
      segment: 'test-results',
      title: 'Test Results',
      icon: <AssessmentIcon />,
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <AssignmentIcon />,
    },
    {
      kind: 'page',
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon />,
      requireSuperuser: true,
    },
    {
      kind: 'header',
      title: 'Settings',
    },
    {
      kind: 'page',
      segment: 'integrations',
      title: 'Integrations',
      icon: <IntegrationInstructionsIcon />,
      requireSuperuser: true,
      children: [
        {
          kind: 'page',
          segment: 'models',
          title: 'Models',
          icon: <SmartToyIcon />,
        },
        {
          kind: 'page',
          segment: 'applications',
          title: 'Applications',
          icon: <GridViewIcon />,
        },
        {
          kind: 'page',
          segment: 'tools',
          title: 'Tools',
          icon: <TerminalIcon />,
        },
      ],
    },
    {
      kind: 'page',
      segment: 'tokens',
      title: 'API Tokens',
      icon: <VpnKeyIcon />,
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
};

export default async function RootLayout(props: { children: React.ReactNode }) {
  const session = await auth().catch(() => null);

  // Get navigation with dynamic organization name
  const navigation = await getNavigationItems(session);

  // Check if local auth is enabled - if true, hide logout button by not providing signOut
  const isLocalAuthEnabled = process.env.NEXT_PUBLIC_LOCAL_AUTH_ENABLED === 'true';
  
  const AUTHENTICATION: AuthenticationProps = {
    signIn: handleSignIn,
    signOut: isLocalAuthEnabled ? undefined : handleSignOut,
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
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
