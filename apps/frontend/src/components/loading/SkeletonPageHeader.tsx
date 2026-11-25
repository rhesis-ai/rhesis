'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import {
  PageBreadcrumbs,
  PageDescription,
  PageTitle,
  type BreadcrumbItem,
} from '@/components/layout/PageLayout';
import type { ActionGate } from '@/constants/page-headers';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';
import { FAB_GROUP_GAP, FAB_SIZE } from '@/styles/theme-constants';
import { can } from '@/utils/affordances';
import { delayedRevealSx } from './DelayedReveal';
import { skeletonTextSx } from './skeletonText';

/**
 * The `PageLayout` header every page skeleton starts with: optional
 * breadcrumbs, a title row with the FAB cluster, and a description line.
 *
 * Text the route already knows (a directory page's title and description, a
 * detail page's first crumb) is drawn for real through PageLayout's own pieces
 * and shows at once. Only what depends on data or page state (entity names,
 * the FAB cluster) is a skeleton, held back like the rest of the fallback.
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
  /** FAB placeholders, matching the page's action cluster. Ignored when
   *  `actions` is given. */
  actionCount?: number;
  /** The page's header buttons and what each needs; one placeholder is drawn
   *  per button this user will get. */
  actions?: readonly ActionGate[];
  /** Breadcrumb segments, known ones included. 0 renders no trail, as list
   *  pages have none. */
  breadcrumbCount?: number;
  titleWidth?: number;
  /** 0 renders no description line. */
  descriptionWidth?: number;
  /** Known leading crumbs, drawn for real; the rest of `breadcrumbCount` are
   *  placeholders. */
  crumbs?: BreadcrumbItem[];
  /** Known title, drawn for real instead of a placeholder. */
  title?: string;
  /** Known description, drawn for real instead of a placeholder. */
  description?: string;
}

/** Buttons out of `actions` this user gets, with `useCan`'s rules: none while
 *  permissions load, all when RBAC is off. */
function useAllowedActionCount(actions: readonly ActionGate[] | undefined) {
  const ambient = useAmbientPermissions();
  if (!actions) return undefined;
  if (ambient.loading) return 0;
  const allowed = (capability: string) =>
    !ambient.enabled || can(ambient, capability);
  return actions.filter(
    gate =>
      gate === null ||
      (typeof gate === 'string' ? allowed(gate) : gate.some(allowed))
  ).length;
}

/** What a route already knows about its header, passed through by the page
 *  skeletons; a `PAGE_HEADERS` entry fits as is. */
export type LoadingHeader = Pick<
  SkeletonPageHeaderProps,
  'title' | 'description' | 'actions' | 'crumbs'
>;

function SkeletonCrumb({ width, last }: { width: number; last: boolean }) {
  return (
    <Box
      sx={{ display: 'flex', alignItems: 'center', gap: BREADCRUMB.itemGap }}
      aria-hidden
    >
      <Skeleton
        variant="text"
        width={width}
        sx={{ ...skeletonTextSx('bodyMReg'), ...delayedRevealSx }}
      />
      {!last && (
        <Skeleton
          variant="circular"
          width={BREADCRUMB.separatorSize}
          height={BREADCRUMB.separatorSize}
          sx={delayedRevealSx}
        />
      )}
    </Box>
  );
}

function Breadcrumbs({
  known,
  count,
}: {
  known: BreadcrumbItem[];
  count: number;
}) {
  const pendingKeys = Array.from(
    { length: Math.max(count - known.length, 0) },
    (_, i) => `crumb-${known.length + i}`
  );
  const pending = pendingKeys.map((key, idx) => (
    <SkeletonCrumb
      key={key}
      width={
        known.length + idx === 0 ? BREADCRUMB.firstWidth : BREADCRUMB.restWidth
      }
      last={idx === pendingKeys.length - 1}
    />
  ));

  if (known.length > 0) {
    return (
      <PageBreadcrumbs
        items={known}
        pending={pending.length > 0 ? pending : undefined}
      />
    );
  }
  return (
    <Box
      sx={{ display: 'flex', alignItems: 'center', gap: BREADCRUMB.gap }}
      aria-hidden
    >
      {pending}
    </Box>
  );
}

export default function SkeletonPageHeader({
  actionCount: fixedActionCount = 2,
  actions,
  breadcrumbCount = 0,
  titleWidth = 180,
  descriptionWidth = 420,
  crumbs = [],
  title,
  description,
}: SkeletonPageHeaderProps = {}) {
  const actionCount = useAllowedActionCount(actions) ?? fixedActionCount;
  const fabKeys = Array.from({ length: actionCount }, (_, i) => `fab-${i}`);

  const titleBlock = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        width: '100%',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: HEADER.titleGap,
          width: '100%',
          minHeight: HEADER.rowHeight,
        }}
      >
        {title ? (
          <PageTitle>{title}</PageTitle>
        ) : (
          <Skeleton
            variant="text"
            width={titleWidth}
            sx={{ ...skeletonTextSx('h4'), ...delayedRevealSx }}
          />
        )}
        {actionCount > 0 && (
          <Box
            sx={{ display: 'flex', gap: FAB_GROUP_GAP, flexShrink: 0 }}
            aria-hidden
          >
            {fabKeys.map(key => (
              <Skeleton
                key={key}
                variant="circular"
                width={FAB_SIZE}
                height={FAB_SIZE}
                sx={delayedRevealSx}
              />
            ))}
          </Box>
        )}
      </Box>
      {description ? (
        <PageDescription>{description}</PageDescription>
      ) : (
        descriptionWidth > 0 && (
          <Skeleton
            variant="text"
            width={descriptionWidth}
            sx={{ ...skeletonTextSx('bodyLReg'), ...delayedRevealSx }}
          />
        )
      )}
    </Box>
  );

  // PageLayout only introduces the 20px stack gap when breadcrumbs are present.
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        ...(breadcrumbCount > 0 && { gap: HEADER.stackGap }),
        mb: HEADER.marginBottom,
      }}
    >
      {breadcrumbCount > 0 && (
        <Breadcrumbs known={crumbs} count={breadcrumbCount} />
      )}
      {titleBlock}
    </Box>
  );
}
