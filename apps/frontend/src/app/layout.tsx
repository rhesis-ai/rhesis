import * as React from 'react';
import { Metadata } from 'next';
import Image from 'next/image';
import { Box } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ScienceIcon from '@mui/icons-material/Science';
import AppsIcon from '@mui/icons-material/Apps';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import BusinessIcon from '@mui/icons-material/Business';
import GroupIcon from '@mui/icons-material/Group';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AssessmentIcon from '@mui/icons-material/Assessment';
import DescriptionIcon from '@mui/icons-material/Description';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import CategoryIcon from '@mui/icons-material/Category';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import IntegrationInstructionsIcon from '@mui/icons-material/IntegrationInstructions';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import GridViewIcon from '@mui/icons-material/GridView';
import ApiIcon from '@mui/icons-material/Api';
import TerminalIcon from '@mui/icons-material/Terminal';
import { auth } from '../auth';
import { handleSignIn, handleSignOut } from '../actions/auth';
import { LayoutContent } from '../components/layout/LayoutContent';
import { ApiClientFactory } from '../utils/api-client/client-factory';
import { type NavigationItem, type BrandingProps, type AuthenticationProps } from '../types/navigation';
import { type Session } from 'next-auth';
import ThemeContextProvider from '../components/providers/ThemeProvider';

// This function will be used to get navigation items with dynamic data
async function getNavigationItems(session: Session | null): Promise<NavigationItem[]> {
  'use server';
  
  // Default organization name if no org found
  let organizationName = 'Organization';
  
  // Fetch organization name if user has an organization_id
  if (session?.user?.organization_id && session?.session_token) {
    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const organizationsClient = clientFactory.getOrganizationsClient();
      const organization = await organizationsClient.getOrganization(session.user.organization_id);
      if (organization?.name) {
        organizationName = organization.name;
      }
    } catch (error) {
      console.error('Error fetching organization:', error);
      // Continue with default organization name
    }
  }
  
  return [
    {
      kind: 'page',
      segment: 'organizations',
      title: organizationName,
      icon: <BusinessIcon />,
      children: [
        {
          kind: 'page',
          segment: 'organizations/team',
          title: 'Team',
          icon: <GroupIcon />,
        },
        {
          kind: 'page',
          segment: 'organizations/risks',
          title: 'Risks',
          icon: <WarningAmberIcon />,
        },
        {
          kind: 'page',
          segment: 'organizations/knowledge',
          title: 'Knowledge',
          icon: <MenuBookIcon />,
          requireSuperuser: true,
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
      segment: 'projects-legacy',
      title: 'Projects Wizard',
      icon: <AutoFixHighIcon />,
      requireSuperuser: true,
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
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon />,
      requireSuperuser: true,
    },
    {
      kind: 'page',
      segment: 'reports',
      title: 'Reports',
      icon: <DescriptionIcon />,
      requireSuperuser: true,
    },
    {
      kind: 'header',
      title: 'Settings',
    },
    {
      kind: 'page',
      segment: 'endpoints',
      title: 'Endpoints',
      icon: <ApiIcon />,
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
        {
          kind: 'page',
          segment: 'llm-providers',
          title: 'LLM Providers',
          icon: <SmartToyIcon />,
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
    icon: '/rhesis-favicon.png',
  },
};

const BRANDING: BrandingProps = {
  title: "",
  logo: (
    <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      <Image
        src="/rhesis-logo-white.png"
        alt="Rhesis Icon"
        width={120}
        height={24}
        style={{ width: 'auto' }}
      />
    </Box>
  ),
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
