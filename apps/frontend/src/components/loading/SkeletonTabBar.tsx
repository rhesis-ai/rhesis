'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS, rem } from '@/styles/theme-constants';
import { skeletonTextSx } from './skeletonText';

/** Tab bar, mirroring `DetailTabNav`. */
const TABS = {
  /** Gap between tabs; DetailTabNav's default `tabGap`. */
  gap: '50px',
  /** Gap between wrapped rows on narrow screens, in MUI spacing units. */
  rowGap: 1.5,
  /** Gap between a label and its underline. */
  labelGap: '8px',
  /** Padding above and below each tab. */
  tabPadding: '5px',
  /** An 18px bold tab label. */
  labelFontSize: rem(18),
  labelLineHeight: rem(25),
  /** A tab icon: 20px, 8px gap, pulled 4px towards the label. */
  iconSize: 20,
  iconGap: '8px',
  iconPull: '-4px',
  /** A count badge (GridBadge, grid size): 12px text in a 22px pill. */
  badgeWidth: 28,
  badgeHeight: 22,
  /** Height of the active tab's underline. */
  underlineHeight: 3,
  /** The underline is a solid bar in the real nav; dim it so it reads as a placeholder. */
  underlineOpacity: 0.35,
} as const;

/** A tab as the page draws it: its label, and whether it carries an icon
 *  before it or a count badge after it. */
export interface SkeletonTabSpec {
  label: string;
  icon?: boolean;
  badge?: boolean;
}

export type SkeletonTab = string | number | SkeletonTabSpec;

const tabKey = (tab: SkeletonTab) =>
  typeof tab === 'object' ? tab.label : String(tab);

function LabelPlaceholder({ tab }: { tab: string | number }) {
  if (typeof tab === 'number') {
    return <Skeleton variant="text" width={tab} sx={skeletonTextSx('h6')} />;
  }
  // A Skeleton with children takes their size; the text stays hidden.
  return (
    <Skeleton variant="text" sx={skeletonTextSx('h6')}>
      <Box
        component="span"
        sx={{
          fontSize: TABS.labelFontSize,
          fontWeight: 700,
          lineHeight: TABS.labelLineHeight,
          whiteSpace: 'nowrap',
        }}
      >
        {tab}
      </Box>
    </Skeleton>
  );
}

export interface SkeletonTabBarProps {
  /**
   * The page's tabs, in order. A label sizes its placeholder to the real
   * label's width; a number gives a width for pages whose tabs aren't known.
   * Entries must be distinct (they key the tabs).
   */
  tabs: readonly SkeletonTab[];
  /** Index of the tab drawn as active; -1 for none. */
  active?: number;
  sx?: SxProps<Theme>;
}

/** A `DetailTabNav` placeholder: one bar per tab at the nav's own geometry. */
export default function SkeletonTabBar({
  tabs,
  active = 0,
  sx,
}: SkeletonTabBarProps) {
  return (
    <Box
      sx={[
        {
          display: 'flex',
          flexWrap: 'wrap',
          columnGap: TABS.gap,
          rowGap: TABS.rowGap,
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      aria-hidden
    >
      {tabs.map((tab, idx) => (
        <Box
          key={tabKey(tab)}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: TABS.labelGap,
            py: TABS.tabPadding,
          }}
        >
          <Box
            sx={{
              height: TABS.labelLineHeight,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {typeof tab === 'object' ? (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: TABS.iconGap,
                }}
              >
                {tab.icon && (
                  <Skeleton
                    variant="circular"
                    width={TABS.iconSize}
                    height={TABS.iconSize}
                    sx={{ mr: TABS.iconPull, flexShrink: 0 }}
                  />
                )}
                <LabelPlaceholder tab={tab.label} />
                {tab.badge && (
                  <Skeleton
                    variant="rounded"
                    width={TABS.badgeWidth}
                    height={TABS.badgeHeight}
                    sx={{ borderRadius: BORDER_RADIUS.pill }}
                  />
                )}
              </Box>
            ) : (
              <LabelPlaceholder tab={tab} />
            )}
          </Box>
          <Box
            sx={{
              height: TABS.underlineHeight,
              borderRadius: BORDER_RADIUS.xs,
              bgcolor: idx === active ? 'primary.main' : 'transparent',
              opacity: idx === active ? TABS.underlineOpacity : 0,
            }}
          />
        </Box>
      ))}
    </Box>
  );
}
