'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  IconButton,
  Link as MuiLink,
  Typography,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import NextLink from 'next/link';
import { useUsage } from '@/contexts/UsageContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { UPGRADE_URL, type QuotaResource } from '@/constants/quota';
import {
  findWorstResource,
  isCommunityEdition,
  quotaCopy,
} from '@/utils/quota';

/**
 * Org-wide quota banner. `usage:read` (the same capability `GET /usage`
 * enforces) is granted to every org member, not just admins -- quota
 * enforcement blocks members too, and hiding the reason from them only
 * turns a 402 into a support ticket (see `auth/rbac.py`'s comment on
 * `Usage.READ`). So this banner is visible to anyone in the org; only the
 * "Upgrade" link is narrower, gated on `Organization.UPDATE` below.
 */
export default function QuotaBanner() {
  const theme = useTheme();
  const { resources, edition, loading } = useUsage();
  const canManageOrg = useCan(Capability.Organization.UPDATE);
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

  const { item, zone } = worst;
  // Never reached with `limit === null` -- `findWorstResource` only flags
  // resources whose zone isn't `healthy`, which requires a non-null limit.
  const limit = item.limit ?? 0;
  const canUpgrade =
    canManageOrg && edition !== null && isCommunityEdition(edition);
  const { sentence } = quotaCopy({
    resource: worst.resource,
    kind: item.kind,
    used: item.used,
    limit,
    zone,
    periodEnd: item.period_end,
    canUpgrade,
  });

  const isDark = theme.palette.mode === 'dark';
  const isBlocked = zone === 'blocked';
  const accent = isBlocked ? theme.palette.error : theme.palette.warning;
  const bgGradient = isDark
    ? `linear-gradient(135deg, ${alpha(accent.dark, 0.85)} 0%, ${alpha(accent.main, 0.7)} 100%)`
    : `linear-gradient(135deg, ${accent.main} 0%, ${accent.light} 100%)`;
  const textColor = accent.contrastText;

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
          {sentence}
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
        {canUpgrade && (
          <MuiLink
            href={UPGRADE_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="caption"
            sx={{
              color: textColor,
              fontWeight: theme => theme.typography.fontWeightBold,
              textDecorationColor: alpha(textColor, 0.5),
            }}
          >
            Upgrade plan →
          </MuiLink>
        )}
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
