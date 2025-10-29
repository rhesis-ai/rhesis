'use client';

import * as React from 'react';
import { DashboardLayout } from '@toolpad/core/DashboardLayout';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { SxProps } from '@mui/system';
import SidebarFooter from '@/components/navigation/SidebarFooter';
import ToolbarActions from '@/components/layout/ToolbarActions';

// Define extended user interface that includes organization_id
interface ExtendedUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const user = session?.user as ExtendedUser | undefined;
  const hasOrganization = !!user?.organization_id;

  // Hide both navigation and AppBar when organization_id is missing
  const layoutStyles: SxProps = {
    ...(hasOrganization
      ? {}
      : {
          //'& header': { display: 'none' },
          '& nav': { display: 'none' },
          '& .MuiDrawer-root': { display: 'none' },
          // Only hide buttons that are part of the toolbar/AppBar, not all buttons
          // But keep buttons with avatars visible
          '& .MuiToolbar-root .MuiButtonBase-root:not(:has(.MuiAvatar-img))': {
            display: 'none',
          },
          '& .MuiToolbar-root .MuiIconButton-root:not(:has(.MuiAvatar-img))': {
            display: 'none',
          },
        }),
  };

  return (
    <AuthErrorBoundary>
      <DashboardLayout
        sx={layoutStyles}
        sidebarExpandedWidth={240}
        slots={{
          sidebarFooter: SidebarFooter,
          toolbarActions: ToolbarActions,
        }}
      >
        {children}
      </DashboardLayout>
    </AuthErrorBoundary>
  );
}
