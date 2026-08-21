'use client';

import { Box, Link as MuiLink, Typography } from '@mui/material';
import NextLink from 'next/link';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { quotaCopy, type QuotaZone } from '@/utils/quota';
import { UPGRADE_URL, type QuotaResource } from '@/constants/quota';
import { BORDER_RADIUS } from '@/styles/theme-constants';

export interface QuotaNoticeProps {
  resource: QuotaResource;
  kind: 'flow' | 'stock' | undefined;
  used: number;
  limit: number;
  zone: Exclude<QuotaZone, 'healthy'>;
  periodEnd?: string;
  canUpgrade: boolean;
}

/**
 * `blocked` reads as an error (something is disabled); `pastIncluded` reads
 * as info (nothing is -- the soft-tier grace band is real, not a warning
 * about to become one); `approaching` splits the difference. Same glyph
 * choices as `NotificationsDrawer`'s `notificationIcon`/`QuotaBanner`, so a
 * zone looks the same wherever it appears.
 */
const ZONE_STYLE = {
  blocked: { Icon: ErrorOutlineIcon, color: 'error.main' as const },
  pastIncluded: { Icon: InfoOutlinedIcon, color: 'primary.main' as const },
  approaching: {
    Icon: WarningAmberOutlinedIcon,
    color: 'warning.main' as const,
  },
};

/**
 * The inline-gate notice: what `BaseDrawer`'s `error` slot renders for a
 * quota gate that isn't a failure. Shared by every drawer's preflight gate
 * and its reactive 402 catch (`parseQuotaError`) -- one place turns a
 * `quotaCopy()` result into markup, so the sentence and recourse always
 * read together the same way.
 *
 * The "Org usage" link is unconditional -- `usage:read` is granted to every
 * member, not just admins, so everyone who can see this notice can also see
 * the numbers behind it. "Upgrade plan" is narrower, matching `canUpgrade`
 * (an org admin on a community-edition org) the same way `QuotaBanner` and
 * the org menu's own upgrade row do.
 */
export function QuotaNotice(props: QuotaNoticeProps) {
  const { zone, canUpgrade } = props;
  const { sentence, recourse } = quotaCopy(props);
  const { Icon, color } = ZONE_STYLE[zone];

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        p: 1.5,
        borderRadius: BORDER_RADIUS.sm,
        border: '1px solid',
        borderColor: 'divider',
        borderLeft: '3px solid',
        borderLeftColor: color,
        bgcolor: theme => theme.palette.greyscale.surface2,
      }}
    >
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
        <Icon sx={{ color, fontSize: 18, mt: '1px', flexShrink: 0 }} />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {sentence}
        </Typography>
      </Box>
      {recourse && (
        <Typography variant="caption" color="text.secondary">
          {recourse}
        </Typography>
      )}
      <Box sx={{ display: 'flex', gap: 1.5 }}>
        <MuiLink
          component={NextLink}
          href="/organizations/usage"
          variant="caption"
          sx={{ fontWeight: 700 }}
        >
          Org usage →
        </MuiLink>
        {canUpgrade && (
          <MuiLink
            href={UPGRADE_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="caption"
            sx={{ fontWeight: 700 }}
          >
            Upgrade plan →
          </MuiLink>
        )}
      </Box>
    </Box>
  );
}
