'use client';

import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import type { Theme } from '@mui/material/styles';
import { GridBadge } from '@/components/common/GridBadge';
import { PlanBadge, PlanCrownIcon } from '@/components/common/PlanBadge';
import { UPGRADE_URL } from '@/constants/quota';
import { planLabel } from '@/utils/plan';
import { usePlan } from '@/contexts/FeaturesContext';
import { useCanUpgrade } from '@/hooks/useQuotaGate';
import { useQuickStart } from '@/contexts/QuickStartContext';
import {
  NAV_CARD_ICON_GAP,
  collapsedNavItemSx,
  navCardIconSx,
  navCardRowSx,
} from './sidebar-utils';

interface SidebarPlanRowProps {
  collapsed?: boolean;
}

/** Plan display: [crown] [tier badge] [Upgrade →], or just the crown when collapsed. */
export function SidebarPlanRow({ collapsed = false }: SidebarPlanRowProps) {
  const plan = usePlan();
  const canUpgrade = useCanUpgrade();
  const quickStart = useQuickStart();
  const label = planLabel(plan);
  if (label === null) return null;

  const heading = quickStart ? 'Mode' : 'Plan';
  const badgeLabel = quickStart ? 'Quick Start' : label;
  const icon = quickStart ? (
    <RocketLaunchOutlinedIcon aria-hidden="true" />
  ) : (
    <PlanCrownIcon plan={plan} />
  );

  if (collapsed) {
    return (
      <Tooltip title={`${heading}: ${badgeLabel}`} placement="right">
        <Box
          role="group"
          aria-label={`${heading}: ${badgeLabel}`}
          sx={{
            ...navCardRowSx({ interactive: false }),
            ...collapsedNavItemSx,
            borderBottom: (theme: Theme) =>
              `1px solid ${theme.palette.greyscale.border}`,
          }}
        >
          <Box
            sx={{
              ...navCardIconSx,
              color: (theme: Theme) => theme.palette.greyscale.body,
            }}
          >
            {icon}
          </Box>
        </Box>
      </Tooltip>
    );
  }

  return (
    <Box
      role="group"
      aria-label={`${heading}: ${badgeLabel}`}
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
        {heading}
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
          {icon}
        </Box>

        {quickStart ? (
          <GridBadge label="Quick Start" size="grid" />
        ) : (
          <PlanBadge plan={plan} />
        )}

        {canUpgrade && !quickStart && (
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
