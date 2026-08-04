'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Chip,
  LinearProgress,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import { FilterButton } from '@/components/common/FilterButton';
import { useUsageForPeriod } from '@/hooks/useUsageForPeriod';
import UsageOverviewFilterDrawer from './UsageOverviewFilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  type QuotaResource,
} from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

const COMMUNITY_EDITION = 'community';
const UPGRADE_URL = 'https://rhesis.ai/editions';

function isCommunityEdition(edition: string): boolean {
  return edition.toLowerCase() === COMMUNITY_EDITION;
}

function PlanChip({ edition }: { edition: string }) {
  const label = `${edition.charAt(0).toUpperCase()}${edition.slice(1)} plan`;
  return (
    <Chip
      label={label}
      size="small"
      color={isCommunityEdition(edition) ? 'default' : 'primary'}
      sx={{ borderRadius: BORDER_RADIUS.pill, fontWeight: 600 }}
    />
  );
}

function UpgradeLink() {
  return (
    <Button
      component="a"
      href={UPGRADE_URL}
      target="_blank"
      rel="noopener noreferrer"
      variant="outlined"
      size="small"
      sx={{ borderRadius: BORDER_RADIUS.sm, fontWeight: 600 }}
    >
      Upgrade
    </Button>
  );
}

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

function progressColor(ratio: number): 'success' | 'warning' | 'error' {
  if (ratio >= 1) return 'error';
  if (ratio >= 0.8) return 'warning';
  return 'success';
}

function ResourceMeter({
  label,
  item,
}: {
  label: string;
  item: UsageResourceItem;
}) {
  const { limit } = item;
  const ratio = limit === null ? 0 : limit === 0 ? 1 : item.used / limit;

  return (
    <Box sx={{ mb: 3, '&:last-child': { mb: 0 } }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="baseline"
        sx={{ mb: 0.5 }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {item.used.toLocaleString()}
          {limit === null ? ' (Unlimited)' : ` / ${limit.toLocaleString()}`}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={limit === null ? 0 : Math.min(ratio, 1) * 100}
        color={limit === null ? 'primary' : progressColor(ratio)}
        sx={{
          height: 6,
          borderRadius: 2,
          bgcolor: theme => theme.palette.action.hover,
          '& .MuiLinearProgress-bar': {
            borderRadius: 2,
          },
        }}
      />
    </Box>
  );
}

function ResourceList({
  usage,
}: {
  usage: Readonly<Record<string, UsageResourceItem>>;
}) {
  const entries = QUOTA_RESOURCE_ORDER.filter(resource => usage[resource]);

  return (
    <Box>
      {entries.map(resource => (
        <ResourceMeter
          key={resource}
          label={QUOTA_RESOURCE_LABELS[resource as QuotaResource]}
          item={usage[resource]}
        />
      ))}
    </Box>
  );
}

export default function UsageOverviewTab() {
  const [periodStart, setPeriodStart] = React.useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const { resources, edition, loading, error } = useUsageForPeriod(periodStart);

  const headerActions = (
    <Stack direction="row" spacing={1.5} alignItems="center">
      {edition && <PlanChip edition={edition} />}
      {edition && isCommunityEdition(edition) && <UpgradeLink />}
      <FilterButton
        onClick={() => setDrawerOpen(true)}
        hasActiveFilters={periodStart !== null}
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

  const anyResource = Object.values(resources)[0];
  const periodLabel = anyResource
    ? `${formatPeriodDate(anyResource.period_start)} – ${formatPeriodDate(anyResource.period_end)}`
    : null;
  const periodPrefix =
    periodStart === null ? 'Current billing period' : 'Billing period';

  return (
    <SectionCard
      title="Usage"
      subtitle={periodLabel ? `${periodPrefix}: ${periodLabel}` : undefined}
      actions={headerActions}
    >
      <ResourceList usage={resources} />
    </SectionCard>
  );
}
