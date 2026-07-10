'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  type StandaloneGroup,
  type SectionGroup,
  collapsedNavItemSx,
  collapsedNavGroupSx,
} from './sidebar-utils';

/** Stable-ish key for a nav group (section title, or the standalone segments). */
function groupKey(group: StandaloneGroup | SectionGroup): string {
  return group.type === 'section'
    ? `section-${group.header.title}`
    : `standalone-${group.items.map(i => i.segment).join('-')}`;
}

/**
 * Placeholder shown in place of the main nav while the ambient permission set
 * is still resolving (the `GET /features` / `/me/permissions` window). Nav
 * items can't decide visibility until then; rendering skeletons that mirror the
 * real group structure avoids both an empty-sidebar flash and a layout shift
 * when the real, permission-filtered items swap in.
 */

function NavItemSkeleton({ collapsed }: { collapsed: boolean }) {
  if (collapsed) {
    return (
      <Skeleton
        variant="rounded"
        sx={{ ...collapsedNavItemSx, borderRadius: BORDER_RADIUS.sm }}
      />
    );
  }
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        px: '14px',
        py: '8px',
      }}
    >
      <Skeleton
        variant="rounded"
        width={24}
        height={24}
        sx={{ flexShrink: 0 }}
      />
      <Skeleton variant="text" sx={{ flex: 1, fontSize: 14 }} />
    </Box>
  );
}

export function NavSkeleton({
  groups,
  collapsed,
}: {
  groups: (StandaloneGroup | SectionGroup)[];
  collapsed: boolean;
}) {
  return (
    <>
      {groups.map(group => {
        const key = groupKey(group);
        return (
          <Box
            key={key}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              ...(collapsed ? collapsedNavGroupSx : {}),
            }}
          >
            {/* Section header placeholder (headers are hidden when collapsed) */}
            {group.type === 'section' && !collapsed && (
              <Box sx={{ px: '14px' }}>
                <Skeleton variant="text" width="40%" sx={{ fontSize: 12 }} />
              </Box>
            )}
            {group.items.map(item => (
              <NavItemSkeleton
                key={`${key}-${item.segment}`}
                collapsed={collapsed}
              />
            ))}
          </Box>
        );
      })}
    </>
  );
}

export default NavSkeleton;
