'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { FAB_GROUP_GAP, FAB_SIZE } from '@/styles/theme-constants';
import { skeletonTextSx } from './skeletonText';

/**
 * The `PageLayout` header every page skeleton starts with: optional
 * breadcrumbs, a title row with the FAB cluster, and a description line.
 *
 * Shared so the four page skeletons cannot drift from each other or from
 * `PageLayout`, whose geometry these constants mirror.
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

export interface SkeletonPageHeaderProps {
  /** FAB placeholders, matching the page's action cluster. */
  actionCount?: number;
  /** Breadcrumb segments. 0 renders no trail, as list pages have none. */
  breadcrumbCount?: number;
  titleWidth?: number;
  /** 0 renders no description line. */
  descriptionWidth?: number;
}

export default function SkeletonPageHeader({
  actionCount = 2,
  breadcrumbCount = 0,
  titleWidth = 180,
  descriptionWidth = 420,
}: SkeletonPageHeaderProps = {}) {
  const fabKeys = Array.from({ length: actionCount }, (_, i) => `fab-${i}`);
  const crumbKeys = Array.from(
    { length: breadcrumbCount },
    (_, i) => `crumb-${i}`
  );

  const titleBlock = (
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
        <Skeleton variant="text" width={titleWidth} sx={skeletonTextSx('h4')} />
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
      {descriptionWidth > 0 && (
        <Skeleton
          variant="text"
          width={descriptionWidth}
          sx={skeletonTextSx('bodyLReg')}
        />
      )}
    </Box>
  );

  // PageLayout only introduces the 20px stack gap when breadcrumbs are present.
  if (crumbKeys.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          mb: HEADER.marginBottom,
        }}
        aria-hidden
      >
        {titleBlock}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: HEADER.stackGap,
        mb: HEADER.marginBottom,
      }}
      aria-hidden
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: BREADCRUMB.gap }}>
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
      {titleBlock}
    </Box>
  );
}
