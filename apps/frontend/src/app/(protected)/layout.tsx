'use client';

import * as React from 'react';
import { DashboardLayout } from '@toolpad/core/DashboardLayout';
import { DashboardSidebarPageItem } from '@toolpad/core/DashboardLayout';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { SxProps, Theme } from '@mui/system';
import { alpha } from '@mui/material/styles';
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
        return <DashboardSidebarPageItem item={item} href={item.__href} />;
      }
      // Default rendering for regular page items
      return <DashboardSidebarPageItem item={item} />;
    },
    []
  );

  // Hide both navigation and AppBar when organization_id is missing
  const layoutStyles: SxProps<Theme> = {
    ...(hasOrganization
      ? {
          // Make sidebar more compact - reduce padding/margins only
          '& .MuiDrawer-root': {
            '& .MuiListItemButton-root': {
              paddingTop: (theme: Theme) => theme.spacing(0.25),
              paddingBottom: (theme: Theme) => theme.spacing(0.25),
              paddingLeft: (theme: Theme) => theme.spacing(1.5),
              paddingRight: (theme: Theme) => theme.spacing(1.5),
              minHeight: '36px',
              maxHeight: '42px',
            },
            '& .MuiListItemIcon-root': {
              minWidth: '32px',
              '& svg': {
                width: '18px',
                height: '18px',
              },
            },
            '& .MuiListItemText-root': {
              margin: 0,
              '& .MuiTypography-root': {
                fontSize: (theme: Theme) =>
                  (theme.typography as any)?.body2?.fontSize || '0.875rem',
                lineHeight: '1.2',
              },
            },
            '& .MuiListSubheader-root': {
              paddingTop: (theme: Theme) => theme.spacing(3),
              paddingBottom: (theme: Theme) => theme.spacing(1),
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
              marginTop: (theme: Theme) => theme.spacing(3),
              marginBottom: (theme: Theme) => theme.spacing(3),
            },
            '& .MuiList-root': {
              paddingTop: (theme: Theme) => theme.spacing(0.25),
              paddingBottom: (theme: Theme) => theme.spacing(0.25),
            },
            '& .MuiCollapse-root .MuiListItemButton-root': {
              paddingLeft: (theme: Theme) => theme.spacing(3.5),
            },
            // Make "Star Rhesis" button flashy and inviting - orange outline style
            '& .MuiListItemButton-root:has(.star-rhesis-icon)': {
              background: 'transparent',
              border: (theme: Theme) =>
                `2px solid ${theme.palette.secondary.main}`,
              borderRadius: (theme: Theme) => theme.shape.borderRadius,
              margin: (theme: Theme) => theme.spacing(0.5, 1),
              padding: (theme: Theme) =>
                `${theme.spacing(0.75, 1.25)} !important`,
              transition: 'all 0.3s ease',
              boxShadow: (theme: Theme) =>
                theme.palette.mode === 'light'
                  ? `0 2px 12px ${alpha(theme.palette.secondary.main, 0.15)}, 0 1px 4px ${alpha(theme.palette.secondary.main, 0.1)}`
                  : `0 4px 16px ${alpha(theme.palette.secondary.main, 0.4)}, 0 2px 8px ${alpha(theme.palette.secondary.main, 0.2)}`,
              '&:hover': {
                background: (theme: Theme) =>
                  alpha(
                    theme.palette.secondary.main,
                    theme.palette.mode === 'light' ? 0.1 : 0.15
                  ),
                borderColor: (theme: Theme) => theme.palette.secondary.main,
                transform: 'translateY(-2px)',
                boxShadow: (theme: Theme) =>
                  theme.palette.mode === 'light'
                    ? `0 4px 16px ${alpha(theme.palette.secondary.main, 0.25)}, 0 2px 6px ${alpha(theme.palette.secondary.main, 0.15)}`
                    : `0 6px 20px ${alpha(theme.palette.secondary.main, 0.45)}, 0 3px 10px ${alpha(theme.palette.secondary.main, 0.25)}`,
              },
              '& .MuiListItemIcon-root': {
                color: (theme: Theme) =>
                  `${theme.palette.secondary.main} !important`,
              },
              '& .MuiListItemText-root .MuiTypography-root': {
                fontWeight: 600,
              },
            },
          },
          // Make header more compact
          '& .MuiToolbar-root': {
            minHeight: '56px',
            paddingTop: (theme: Theme) => theme.spacing(1),
            paddingBottom: (theme: Theme) => theme.spacing(1),
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
