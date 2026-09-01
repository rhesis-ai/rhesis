'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import {
  BORDER_RADIUS,
  ELEVATION,
  FAB_GROUP_GAP,
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

const HEADER_ROW_HEIGHT = 56;
const TAB_UNDERLINE_HEIGHT = 3;

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
        sx={{ display: 'flex', flexDirection: 'column', gap: '20px', mb: 5 }}
        aria-hidden
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {crumbKeys.map((key, idx) => (
            <Box
              key={key}
              sx={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Skeleton
                variant="text"
                width={idx === 0 ? 72 : 108}
                sx={skeletonTextSx('bodyMReg')}
              />
              {idx < crumbKeys.length - 1 && (
                <Skeleton variant="circular" width={6} height={6} />
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
              gap: '16px',
              minHeight: HEADER_ROW_HEIGHT,
            }}
          >
            <Skeleton variant="text" width={280} sx={skeletonTextSx('h4')} />
            {actionCount > 0 && (
              <Box sx={{ display: 'flex', gap: FAB_GROUP_GAP, flexShrink: 0 }}>
                {fabKeys.map(key => (
                  <Skeleton
                    key={key}
                    variant="circular"
                    width={56}
                    height={56}
                  />
                ))}
              </Box>
            )}
          </Box>
          <Skeleton
            variant="text"
            width={460}
            sx={skeletonTextSx('bodyLReg')}
          />
        </Box>
      </Box>

      {/* DetailTabNav: 18px labels at 50px gaps, active tab underlined */}
      <Box sx={{ display: 'flex', gap: '50px' }} aria-hidden>
        {TAB_WIDTHS.map((width, idx) => (
          <Box
            key={width}
            sx={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
          >
            <Skeleton variant="text" width={width} sx={skeletonTextSx('h6')} />
            <Box
              sx={{
                height: TAB_UNDERLINE_HEIGHT,
                borderRadius: BORDER_RADIUS.xs,
                bgcolor: idx === 0 ? 'primary.main' : 'transparent',
                opacity: idx === 0 ? 0.35 : 0,
              }}
            />
          </Box>
        ))}
      </Box>

      {/* Tab panel content: DetailTabPanel applies pt: 5 */}
      <Box
        sx={{ pt: 5, display: 'flex', flexDirection: 'column', gap: 3 }}
        aria-hidden
      >
        {SECTIONS.map(section => (
          <Box
            key={section.key}
            sx={{
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              bgcolor: 'background.paper',
              p: '30px',
            }}
          >
            <Skeleton
              variant="text"
              width={section.heading}
              sx={{ ...skeletonTextSx('h6'), mb: 3 }}
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
                    width={96}
                    sx={skeletonTextSx('bodySReg')}
                  />
                  <Skeleton
                    variant="text"
                    width="72%"
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
