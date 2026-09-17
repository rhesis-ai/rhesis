'use client';

import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import { PlanBadge, PlanCrownIcon } from '@/components/common/PlanBadge';
import { UPGRADE_URL } from '@/constants/quota';
import { planLabel } from '@/utils/plan';
import { usePlan } from '@/contexts/FeaturesContext';
import { useCanUpgrade } from '@/hooks/useQuotaGate';
import {
  NAV_CARD_ICON_GAP,
  navCardIconSx,
  navCardRowSx,
} from './sidebar-utils';

/** Single-row plan display: [crown] [tier badge] [Upgrade →]. */
export function SidebarPlanRow() {
  const plan = usePlan();
  const canUpgrade = useCanUpgrade();
  const label = planLabel(plan);
  if (label === null) return null;

  return (
    <Box
      // One labelled unit rather than three loose bits of text, so the tier is
      // announced with what it describes: "Plan: Community". The crown is
      // aria-hidden, since colour and fill are not information a screen reader
      // can use.
      role="group"
      aria-label={`Plan: ${label}`}
      sx={{
        ...navCardRowSx({ interactive: false }),
        flexDirection: 'column',
        alignItems: 'stretch',
        borderBottom: (theme: Theme) =>
          `1px solid ${theme.palette.greyscale.border}`,
      }}
    >
      <Typography
        variant="caption"
        sx={{ color: (theme: Theme) => theme.palette.greyscale.subtitle }}
      >
        Plan
      </Typography>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: NAV_CARD_ICON_GAP,
        }}
      >
        <Box
          sx={{
            ...navCardIconSx,
            color: (theme: Theme) => theme.palette.greyscale.body,
          }}
        >
          <PlanCrownIcon plan={plan} />
        </Box>

        <PlanBadge plan={plan} />

        {canUpgrade && (
          <MuiLink
            href={UPGRADE_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="caption"
            sx={{
              fontWeight: (theme: Theme) =>
                theme.typography.captionBold.fontWeight,
              ml: 'auto',
            }}
          >
            Upgrade →
          </MuiLink>
        )}
      </Box>
    </Box>
  );
}

export default SidebarPlanRow;
