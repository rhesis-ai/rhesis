'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import {
  BORDER_RADIUS,
  GRID_CARD_INSET,
  SECTION_GRID,
} from '@/styles/theme-constants';
import DelayedReveal from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonSurfaceSx } from './skeletonSurface';
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

/** Placeholder widths for the header text. Layout geometry lives in
 *  SkeletonPageHeader, which mirrors PageLayout. */
const HEADER = {
  titleWidth: 280,
  descriptionWidth: 460,
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
  /** Breadcrumb segments before the current page. 0 renders no trail. */
  breadcrumbCount?: number;
  /**
   * Render the DetailTabNav bar. Settings-style pages stack their section
   * cards straight under the header with no tab bar, so they pass false and
   * also drop the DetailTabPanel top inset that the bar would sit above.
   */
  showTabs?: boolean;
}

export default function PageDetailSkeleton({
  actionCount = 2,
  breadcrumbCount = 2,
  showTabs = true,
}: PageDetailSkeletonProps = {}) {
  return (
    <DelayedReveal>
      <SkeletonPageHeader
        actionCount={actionCount}
        breadcrumbCount={breadcrumbCount}
        titleWidth={HEADER.titleWidth}
        descriptionWidth={HEADER.descriptionWidth}
      />

      {/* DetailTabNav: 18px labels at 50px gaps, active tab underlined */}
      {showTabs && (
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
              <Skeleton
                variant="text"
                width={width}
                sx={skeletonTextSx('h6')}
              />
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
      )}

      {/* Tab panel content: DetailTabPanel applies pt: 5 */}
      <Box
        sx={{
          pt: showTabs ? SECTION.panelTop : 0,
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
              ...skeletonSurfaceSx,
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
    </DelayedReveal>
  );
}
