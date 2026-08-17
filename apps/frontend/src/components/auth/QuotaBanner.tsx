'use client';

import { useMemo, useState } from 'react';
import { Box, IconButton, Link as MuiLink, Typography, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import NextLink from 'next/link';
import { useUsage } from '@/contexts/UsageContext';
import { QUOTA_RESOURCE_LABELS, type QuotaResource } from '@/constants/quota';

/** Utilization at or above this fraction surfaces the banner. */
const WARNING_THRESHOLD = 0.8;

interface WorstResource {
  resource: QuotaResource;
  used: number;
  limit: number;
  ratio: number;
}

/**
 * Finds the single resource closest to (or past) its limit, or `null` if
 * every resource is comfortably under `WARNING_THRESHOLD`.
 *
 * Only one resource is surfaced at a time -- stacking a banner per
 * over-threshold resource would compete with `VerificationBanner` and the
 * app chrome for the same header space. A resource with `limit: null`
 * (unlimited) never contributes: there is no ratio to compute.
 *
 * `limit: 0` is a real configured value meaning "none allowed", not a
 * missing limit, so it reports as fully consumed rather than being skipped
 * -- skipping it hid the banner from precisely the orgs that were already
 * blocked. Matches `UsageOverviewTab`'s handling of the same case.
 *
 * Resources with no label are skipped: the backend can add a `QuotaResource`
 * before `constants/quota.ts` catches up, and this component renders inside
 * the protected layout, so a missing label would throw on every page rather
 * than just this banner.
 */
function findWorstResource(
  resources: Readonly<Record<string, { used: number; limit: number | null }>>
): WorstResource | null {
  let worst: WorstResource | null = null;
  for (const [resource, item] of Object.entries(resources)) {
    if (item.limit === null || item.limit < 0) continue;
    if (!(resource in QUOTA_RESOURCE_LABELS)) continue;
    const ratio = item.limit === 0 ? 1 : item.used / item.limit;
    if (ratio >= WARNING_THRESHOLD && (!worst || ratio > worst.ratio)) {
      worst = { resource: resource as QuotaResource, used: item.used, limit: item.limit, ratio };
    }
  }
  return worst;
}

export default function QuotaBanner() {
  const theme = useTheme();
  const { resources, loading } = useUsage();
  const [dismissedFor, setDismissedFor] = useState<QuotaResource | null>(null);

  const worst = useMemo(() => {
    if (loading) return null;
    return findWorstResource(resources);
  }, [resources, loading]);

  // Re-surfaces if a *different* resource crosses the threshold after the
  // current one was dismissed, rather than staying silenced for the rest
  // of the session -- dismissing a spans warning shouldn't also hide a
  // later, unrelated seats warning.
  if (!worst || dismissedFor === worst.resource) {
    return null;
  }

  const label = QUOTA_RESOURCE_LABELS[worst.resource];
  const percent = Math.round(worst.ratio * 100);
  const isDark = theme.palette.mode === 'dark';
  const bgGradient = isDark
    ? `linear-gradient(135deg, ${alpha(theme.palette.warning.dark, 0.85)} 0%, ${alpha(theme.palette.warning.main, 0.7)} 100%)`
    : `linear-gradient(135deg, ${theme.palette.warning.main} 0%, ${theme.palette.warning.light} 100%)`;
  const textColor = theme.palette.warning.contrastText;

  return (
    <Box
      sx={{
        background: bgGradient,
        py: 0.5,
        px: 2,
        minHeight: theme => theme.spacing(4),
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <WarningAmberIcon
          sx={{
            fontSize: theme => theme.typography.body2.fontSize,
            color: textColor,
          }}
        />
        <Typography
          variant="caption"
          sx={{
            color: textColor,
            fontWeight: theme => theme.typography.fontWeightMedium,
          }}
        >
          {`You've used ${percent}% of your ${label.toLowerCase()} limit for this billing period.`}
        </Typography>
        <MuiLink
          component={NextLink}
          href="/organizations/usage"
          variant="caption"
          sx={{
            color: textColor,
            fontWeight: theme => theme.typography.fontWeightBold,
            textDecorationColor: alpha(textColor, 0.5),
          }}
        >
          View usage
        </MuiLink>
      </Box>
      <IconButton
        size="small"
        onClick={() => setDismissedFor(worst.resource)}
        aria-label="Dismiss banner"
        sx={{
          position: 'absolute',
          right: theme => theme.spacing(1),
          color: textColor,
          opacity: 0.8,
          p: 0.25,
          '&:hover': {
            opacity: 1,
            backgroundColor: alpha(textColor, 0.1),
          },
        }}
      >
        <CloseIcon
          sx={{
            fontSize: theme => theme.typography.body2.fontSize,
          }}
        />
      </IconButton>
    </Box>
  );
}
