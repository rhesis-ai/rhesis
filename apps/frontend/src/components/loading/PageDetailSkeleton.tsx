'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { Theme } from '@mui/material/styles';
import {
  BORDER_RADIUS,
  ELEVATION,
  FAB_GROUP_GAP,
  FAB_SIZE,
  GRID_CARD_INSET,
  SECTION_GRID,
} from '@/styles/theme-constants';
import { delayedRevealSx } from './DelayedReveal';
import { skeletonTextSx } from './skeletonText';

/**
 * Loading placeholder for entity detail pages: `PageLayout` header
 * (breadcrumbs, title, description, FAB cluster) above a `DetailTabNav` bar
 * and section cards.
 *
 * Geometry follows the real components: 10px breadcrumb gap and 20px header
 * stack (PageLayout), 56px FABs at `FAB_GROUP_GAP` (Fab.tsx), 50px tab gap
 * with an active-tab underline (DetailTabNav), 40px panel inset
 * (DetailTabPanel `pt: 5`) and `SECTION_GRID` field spacing.
 */

/** Page header, mirroring `PageLayout`. */
const HEADER = {
  /** `minHeight` of the title row. */
  rowHeight: 56,
  /** Gap between the title and the action cluster. */
  titleGap: '16px',
  /** Vertical gap between the breadcrumbs and the title block. */
  stackGap: '20px',
  /** Bottom margin of the whole header block, in MUI spacing units. */
  marginBottom: 5,
  titleWidth: 280,
  descriptionWidth: 460,
} as const;

/** Breadcrumb trail, mirroring `PageBreadcrumbs` in PageLayout. */
const BREADCRUMB = {
  /** Gap between crumbs. */
  gap: '10px',
  /** Gap between a crumb's label and its separator. */
  itemGap: '6px',
  separatorSize: 6,
  firstWidth: 72,
  restWidth: 108,
} as const;

/** Tab bar, mirroring `DetailTabNav`. */
const TABS = {
  /** Gap between tabs; DetailTabNav's default `tabGap`. */
  gap: '50px',
  /** Gap between a label and its underline. */
  labelGap: '8px',
  /** Height of the active tab's underline. */
  underlineHeight: 3,
  /** The underline is a solid bar in the real nav; dim it so it reads as a placeholder. */
  underlineOpacity: 0.35,
} as const;

/** Section cards inside the tab panel. */
const SECTION = {
  /** Inset matching a SectionCard's padding. */
  inset: GRID_CARD_INSET,
  /** Gap between stacked cards, in MUI spacing units. */
  gap: 3,
  /** Inset DetailTabPanel puts above the panel body, in MUI spacing units. */
  panelTop: 5,
  /** Gap below a card heading, in MUI spacing units. */
  headingGap: 3,
  fieldLabelWidth: 96,
  fieldValueWidth: '72%',
} as const;

/** Card border, matching the grid card and SectionCard. */
const cardBorder = (theme: Theme) =>
  `1px solid ${theme.palette.greyscale.border}`;

/** Tab label widths — detail pages run 3-5 tabs (Overview, Test Sets, …). */
const TAB_WIDTHS = [78, 96, 132, 62];

/** Section cards, each with a heading and a 2-column field grid. */
const SECTIONS = [
  { key: 'primary', heading: 150, fields: 6 },
  { key: 'secondary', heading: 190, fields: 4 },
];

export interface PageDetailSkeletonProps {
  /** FAB placeholders in the header, matching the page's action cluster. */
  actionCount?: number;
  /** Breadcrumb segments before the current page. */
  breadcrumbCount?: number;
}

export default function PageDetailSkeleton({
  actionCount = 2,
  breadcrumbCount = 2,
}: PageDetailSkeletonProps = {}) {
  const fabKeys = Array.from({ length: actionCount }, (_, i) => `fab-${i}`);
  const crumbKeys = Array.from(
    { length: breadcrumbCount },
    (_, i) => `crumb-${i}`
  );

  return (
    <Box
      sx={{ width: '100%', ...delayedRevealSx }}
      role="status"
      aria-label="Loading page"
    >
      {/* PageLayout header: breadcrumbs, then title/description block, mb: 5 */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: HEADER.stackGap,
          mb: HEADER.marginBottom,
        }}
        aria-hidden
      >
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: BREADCRUMB.gap }}
        >
          {crumbKeys.map((key, idx) => (
            <Box
              key={key}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: BREADCRUMB.itemGap,
              }}
            >
              <Skeleton
                variant="text"
                width={idx === 0 ? BREADCRUMB.firstWidth : BREADCRUMB.restWidth}
                sx={skeletonTextSx('bodyMReg')}
              />
              {idx < crumbKeys.length - 1 && (
                <Skeleton
                  variant="circular"
                  width={BREADCRUMB.separatorSize}
                  height={BREADCRUMB.separatorSize}
                />
              )}
            </Box>
          ))}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: HEADER.titleGap,
              minHeight: HEADER.rowHeight,
            }}
          >
            <Skeleton
              variant="text"
              width={HEADER.titleWidth}
              sx={skeletonTextSx('h4')}
            />
            {actionCount > 0 && (
              <Box sx={{ display: 'flex', gap: FAB_GROUP_GAP, flexShrink: 0 }}>
                {fabKeys.map(key => (
                  <Skeleton
                    key={key}
                    variant="circular"
                    width={FAB_SIZE}
                    height={FAB_SIZE}
                  />
                ))}
              </Box>
            )}
          </Box>
          <Skeleton
            variant="text"
            width={HEADER.descriptionWidth}
            sx={skeletonTextSx('bodyLReg')}
          />
        </Box>
      </Box>

      {/* DetailTabNav: 18px labels at 50px gaps, active tab underlined */}
      <Box sx={{ display: 'flex', gap: TABS.gap }} aria-hidden>
        {TAB_WIDTHS.map((width, idx) => (
          <Box
            key={width}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: TABS.labelGap,
            }}
          >
            <Skeleton variant="text" width={width} sx={skeletonTextSx('h6')} />
            <Box
              sx={{
                height: TABS.underlineHeight,
                borderRadius: BORDER_RADIUS.xs,
                bgcolor: idx === 0 ? 'primary.main' : 'transparent',
                opacity: idx === 0 ? TABS.underlineOpacity : 0,
              }}
            />
          </Box>
        ))}
      </Box>

      {/* Tab panel content: DetailTabPanel applies pt: 5 */}
      <Box
        sx={{
          pt: SECTION.panelTop,
          display: 'flex',
          flexDirection: 'column',
          gap: SECTION.gap,
        }}
        aria-hidden
      >
        {SECTIONS.map(section => (
          <Box
            key={section.key}
            sx={{
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: cardBorder,
              bgcolor: 'background.paper',
              p: SECTION.inset,
            }}
          >
            <Skeleton
              variant="text"
              width={section.heading}
              sx={{ ...skeletonTextSx('h6'), mb: SECTION.headingGap }}
            />
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                columnGap: SECTION_GRID.columnSpacing,
                rowGap: SECTION_GRID.rowSpacing,
              }}
            >
              {Array.from(
                { length: section.fields },
                (_, i) => `${section.key}-field-${i}`
              ).map(key => (
                <Box key={key}>
                  <Skeleton
                    variant="text"
                    width={SECTION.fieldLabelWidth}
                    sx={skeletonTextSx('bodySReg')}
                  />
                  <Skeleton
                    variant="text"
                    width={SECTION.fieldValueWidth}
                    sx={skeletonTextSx('bodyLReg')}
                  />
                </Box>
              ))}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
