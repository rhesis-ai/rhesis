'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import NextLink from 'next/link';
import { PlanBadge, PlanCrownIcon } from '@/components/common/PlanBadge';
import { planLabel } from '@/utils/plan';
import type { Plan } from '@/utils/api-client/usage-client';
import {
  navCardIconSx,
  navCardLabelSx,
  navCardRowSx,
  navCardTrailingSx,
} from './sidebar-utils';

/** Where the row goes: the plan lives next to the usage it governs, and this
 * is the one page showing both. Internal, and readable by every org member
 * (`usage:read` is not admin-only), so the row never links somewhere the
 * clicker cannot follow. */
const USAGE_HREF = '/organizations/usage';

interface SidebarPlanRowProps {
  /** The org's plan from `GET /usage`, or `null` while it loads. */
  plan: Plan | null | undefined;
}

/**
 * The org's plan, as the first row of the sidebar's footer card.
 *
 * Built from the same row primitives as `NavLinkItem` — `navCardRowSx`,
 * `navCardIconSx`, `navCardLabelSx` — rather than its own layout, so the crown
 * sits in the same icon gutter and "Plan" starts at the same x-offset as
 * "Star Rhesis" and "Support" below it. Those primitives live in
 * `sidebar-utils.ts` and are shared, so the two cannot drift.
 *
 * Structure: `[crown] [label] [spacer] [badge]`. The badge is anchored to the
 * row's right padding edge by `marginLeft: auto` (`navCardTrailingSx`), which
 * puts it at the same x for every tier-name length, and `flexShrink: 0` there
 * plus `minWidth: 0` on the label mean a long name ellipsizes rather than
 * squeezing the badge.
 *
 * Holds no opinion about the plan itself. Naming the tier, deciding whether it
 * is paid, and colouring it are `PlanBadge` / `resolvePlanStyle`'s job, driven
 * off the API's booleans. Nothing here inspects a tier name, so a new tier
 * needs no change to this file.
 *
 * Renders nothing until the plan is known — a plan must not flicker from a
 * placeholder to the real value.
 */
export function SidebarPlanRow({ plan }: SidebarPlanRowProps) {
  if (planLabel(plan) === null) return null;

  return (
    <Box
      component={NextLink}
      href={USAGE_HREF}
      aria-label="Current plan — view usage"
      sx={{
        ...navCardRowSx(),
        // Separates status from the actions below it. The card draws no
        // dividers between its own links, so without this the plan reads as a
        // third thing you could click to do something.
        borderBottom: (theme: Theme) =>
          `1px solid ${theme.palette.greyscale.border}`,
      }}
    >
      <Box
        sx={{
          ...navCardIconSx,
          // Inherits when the resolver returns no crown colour, which is how
          // a free plan's crown matches the sibling rows' icon colour.
          color: (theme: Theme) => theme.palette.greyscale.body,
        }}
      >
        <PlanCrownIcon plan={plan} />
      </Box>

      <Typography
        sx={{
          ...navCardLabelSx,
          color: (theme: Theme) => theme.palette.greyscale.body,
        }}
      >
        Plan
      </Typography>

      <Box sx={navCardTrailingSx}>
        <PlanBadge plan={plan} />
      </Box>
    </Box>
  );
}

export default SidebarPlanRow;
