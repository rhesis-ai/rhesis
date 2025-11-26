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
      ? {
          // Make sidebar more compact - reduce padding/margins only
          '& .MuiDrawer-root': {
            '& .MuiListItemButton-root': {
              paddingTop: '4px',
              paddingBottom: '4px',
              paddingLeft: '12px',
              paddingRight: '12px',
              minHeight: '36px',
              maxHeight: '42px',
            },
            '& .MuiListItemIcon-root': {
              minWidth: '32px',
              '& svg': {
                width: '20px',
                height: '20px',
                fontSize: '16px',
              },
            },
            '& .MuiListItemText-root': {
              margin: 0,
              '& .MuiTypography-root': {
                fontSize: '14px',
                lineHeight: '1.2',
              },
            },
            '& .MuiListSubheader-root': {
              paddingTop: '24px',
              paddingBottom: '8px',
              lineHeight: '1.5',
              height: 'auto',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'block',
            },
            // When drawer is mini/collapsed, ensure headers are truncated properly
            '&.MuiDrawer-docked .MuiListSubheader-root': {
              maxWidth: '100%',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            },
            '& .MuiDivider-root': {
              marginTop: '24px',
              marginBottom: '16px',
            },
            '& .MuiList-root': {
              paddingTop: '2px',
              paddingBottom: '2px',
            },
            '& .MuiCollapse-root .MuiListItemButton-root': {
              paddingLeft: '28px',
            },
          },
          // Make header more compact
          '& .MuiToolbar-root': {
            minHeight: '56px',
            paddingTop: '8px',
            paddingBottom: '8px',
          },
        }
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
