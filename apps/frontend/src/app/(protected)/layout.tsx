'use client';

import * as React from 'react';
import { DashboardLayout } from '@toolpad/core/DashboardLayout';
import { DashboardSidebarPageItem } from '@toolpad/core/DashboardLayout';
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

  // Custom renderer for page items to handle external links
  const renderPageItem = React.useCallback(
    (item: any, options: { mini: boolean }) => {
      // Check if this is an external link (has metadata from NavigationProvider)
      if (item.__isExternalLink && item.__href) {
        return (
          <DashboardSidebarPageItem
            item={item}
            href={item.__href}
          />
        );
      }
      // Default rendering for regular page items
      return <DashboardSidebarPageItem item={item} />;
    },
    []
  );

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
              marginBottom: '24px',
            },
            '& .MuiList-root': {
              paddingTop: '2px',
              paddingBottom: '2px',
            },
            '& .MuiCollapse-root .MuiListItemButton-root': {
              paddingLeft: '28px',
            },
            // Make "Star Rhesis" button flashy and inviting - orange outline style
            '& .MuiListItemButton-root:has(.star-rhesis-icon)': {
              background: 'transparent',
              border: '2px solid #FD6E12',
              borderRadius: '8px',
              margin: '4px 8px',
              padding: '6px 10px !important',
              transition: 'all 0.3s ease',
              boxShadow: '0 2px 2px rgba(26, 11, 2, 0.15)',
              '&:hover': {
                background: 'rgba(253, 110, 18, 0.1)',
                borderColor: '#FD6E12',
                transform: 'translateY(-2px)',
                boxShadow: '0 4px 6px rgba(253, 110, 18, 0.3)',
              },
              '& .MuiListItemIcon-root': {
                color: '#FD6E12 !important',
              },
              '& .MuiListItemText-root .MuiTypography-root': {
                fontWeight: 600,
              },
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
        renderPageItem={renderPageItem}
      >
        {children}
      </DashboardLayout>
    </AuthErrorBoundary>
  );
}
