'use client';

import * as React from 'react';
import {
  Box,
  LinearProgress,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { SectionCard } from '@/components/common/SectionCard';
import { FilterButton } from '@/components/common/FilterButton';
import { UpgradeLink } from '@/components/common/QuotaChips';
import { PlanBadge } from '@/components/common/PlanBadge';
import { useUsageForPeriod } from '@/hooks/useUsageForPeriod';
import UsageOverviewFilterDrawer from './UsageOverviewFilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  type QuotaResource,
} from '@/constants/quota';
import { classifyZone, zoneColor, type QuotaZone } from '@/utils/quota';
import { isUpgradeable } from '@/utils/plan';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

function formatPeriodDate(isoDate: string): string {
  // period_start/period_end are date-only strings (YYYY-MM-DD), computed
  // in UTC by the backend. `new Date(isoDate)` parses that as UTC
  // midnight, so formatting must stay in UTC too -- otherwise
  // toLocaleDateString() converts to the viewer's local time and users
  // west of UTC see the previous day.
  return new Date(isoDate).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

/** Ceiling caption under a meter: names the overage allowance, or says
 * there isn't one. `limit === null` (unlimited) renders nothing -- there is
 * no ceiling to report. */
function CeilingCaption({
  limit,
  ceiling,
}: Pick<UsageResourceItem, 'limit' | 'ceiling'>) {
  if (limit === null) return null;
  if (ceiling === null || ceiling === limit) {
    return (
      <Typography variant="caption" color="text.secondary">
        No overage allowance on this resource
      </Typography>
    );
  }
  return (
    <Typography variant="caption" color="text.secondary">
      {limit.toLocaleString()} included · {ceiling.toLocaleString()} before
      requests fail
    </Typography>
  );
}

/**
 * The bar itself. Fills toward `limit` in the "included" track; when the
 * tier grants an overage allowance (`ceiling > limit`), a second hatched
 * track past it fills as that allowance is consumed. Zero-width on a hard
 * tier, where `ceiling === limit`.
 */
function MeterBar({
  item,
  zone,
}: {
  item: UsageResourceItem;
  zone: QuotaZone;
}) {
  const { used, limit, ceiling } = item;
  const color = zoneColor(zone);

  if (limit === null) {
    return (
      <LinearProgress
        variant="determinate"
        value={0}
        color="primary"
        sx={{
          height: 6,
          borderRadius: BORDER_RADIUS.xs,
          bgcolor: theme => theme.palette.action.hover,
        }}
      />
    );
  }

  const total = ceiling !== null && ceiling > limit ? ceiling : limit;
  const includedPct = total === 0 ? 100 : (limit / total) * 100;
  const includedFill =
    limit === 0 ? 100 : (Math.min(used, limit) / limit) * 100;
  const overageCapacity = total - limit;
  const overageUsed = Math.max(0, used - limit);
  const overageFill =
    overageCapacity > 0
      ? (Math.min(overageUsed, overageCapacity) / overageCapacity) * 100
      : 0;

  return (
    <Box
      sx={{
        display: 'flex',
        height: 6,
        borderRadius: BORDER_RADIUS.xs,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          position: 'relative',
          width: `${includedPct}%`,
          bgcolor: theme => theme.palette.action.hover,
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            width: `${includedFill}%`,
            bgcolor: theme => theme.palette[color].main,
          }}
        />
      </Box>
      {overageCapacity > 0 && (
        <Box
          sx={{
            position: 'relative',
            width: `${100 - includedPct}%`,
            ml: '2px',
            backgroundImage: theme =>
              `repeating-linear-gradient(135deg, ${alpha(theme.palette[color].main, 0.25)} 0 4px, transparent 4px 8px)`,
            bgcolor: theme => theme.palette.action.hover,
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              width: `${overageFill}%`,
              bgcolor: theme => theme.palette[color].main,
            }}
          />
        </Box>
      )}
    </Box>
  );
}

function ResourceMeter({
  label,
  item,
  showLiveCountHint = false,
}: {
  label: string;
  item: UsageResourceItem;
  /**
   * Marks this row as a live count that does *not* belong to the period in
   * the card's heading -- see `ResourceList`.
   */
  showLiveCountHint?: boolean;
}) {
  const { limit } = item;
  const zone = classifyZone(item);

  return (
    <Box sx={{ mb: 3, '&:last-child': { mb: 0 } }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="baseline"
        sx={{ mb: 0.5 }}
      >
        <Stack direction="row" spacing={0.75} alignItems="baseline">
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {label}
          </Typography>
          {showLiveCountHint && (
            <Typography variant="caption" color="text.secondary">
              as of today
            </Typography>
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {item.used.toLocaleString()}
          {limit === null ? ' (Unlimited)' : ` / ${limit.toLocaleString()}`}
        </Typography>
      </Stack>
      <MeterBar item={item} zone={zone} />
      <Box sx={{ mt: 0.5 }}>
        <CeilingCaption limit={item.limit} ceiling={item.ceiling} />
      </Box>
    </Box>
  );
}

function ResourceList({
  usage,
  isPastPeriod,
}: {
  usage: Readonly<Record<string, UsageResourceItem>>;
  isPastPeriod: boolean;
}) {
  const entries = QUOTA_RESOURCE_ORDER.filter(resource => usage[resource]);

  return (
    <Box>
      {entries.map(resource => (
        <ResourceMeter
          key={resource}
          label={QUOTA_RESOURCE_LABELS[resource as QuotaResource]}
          item={usage[resource]}
          // Stock resources have no historical row -- the backend always
          // answers with today's live count, whichever period was asked
          // for. Unlabelled under a past month's heading, "Seats 11 / 3"
          // reads as that month's seat count, so say otherwise.
          showLiveCountHint={isPastPeriod && usage[resource].kind === 'stock'}
        />
      ))}
    </Box>
  );
}

export default function UsageOverviewTab() {
  const [periodStart, setPeriodStart] = React.useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const { resources, plan, loading, error } = useUsageForPeriod(periodStart);

  // The period is the only filter here, so an active one is a count of 1.
  // Passing the number matters: given only the boolean, FilterButton draws
  // the badge with nothing inside it.
  const activeFilterCount = periodStart !== null ? 1 : 0;

  const headerActions = (
    <Stack direction="row" spacing={1.5} alignItems="center">
      <PlanBadge plan={plan} />
      {isUpgradeable(plan) && <UpgradeLink />}
      <FilterButton
        onClick={() => setDrawerOpen(true)}
        hasActiveFilters={activeFilterCount > 0}
        activeFilterCount={activeFilterCount}
      />
      <UsageOverviewFilterDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        periodStart={periodStart}
        onApply={setPeriodStart}
      />
    </Stack>
  );

  if (loading) {
    return (
      <SectionCard title="Usage" actions={headerActions}>
        <Stack spacing={2}>
          {Array.from({ length: 4 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key -- fixed-count skeleton placeholders, never reordered
            <Skeleton key={i} variant="rectangular" height={48} />
          ))}
        </Stack>
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard title="Usage" actions={headerActions}>
        <Typography color="error.main">
          Could not load usage data. Please try again later.
        </Typography>
      </SectionCard>
    );
  }

  // Specifically a *flow* resource: only those carry the requested
  // period. Stock items always report the current one, so picking whatever
  // resource happens to come first would silently start labelling the card
  // with today's dates if the backend's QuotaResource order ever changed.
  const periodSource = Object.values(resources).find(
    item => item.kind === 'flow'
  );
  const periodLabel = periodSource
    ? `${formatPeriodDate(periodSource.period_start)} – ${formatPeriodDate(periodSource.period_end)}`
    : null;
  const isPastPeriod = periodStart !== null;
  const periodPrefix = isPastPeriod ? 'Usage period' : 'Current usage period';

  return (
    <SectionCard
      title="Usage"
      subtitle={periodLabel ? `${periodPrefix}: ${periodLabel}` : undefined}
      actions={headerActions}
    >
      <ResourceList usage={resources} isPastPeriod={isPastPeriod} />
    </SectionCard>
  );
}
