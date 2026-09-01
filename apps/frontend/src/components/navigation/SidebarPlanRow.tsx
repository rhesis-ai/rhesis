'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import NextLink from 'next/link';
import { PlanChip } from '@/components/common/QuotaChips';
import { BORDER_RADIUS } from '@/styles/theme';
import { NAV_CARD_STATUS_ROW_SX } from './sidebar-utils';

/** Where the row goes: the plan lives next to the usage it governs, and this
 * is the one page that shows both. Internal, and readable by every org member
 * (`usage:read` is not admin-only), so the row never links somewhere the
 * clicker cannot follow. */
const USAGE_HREF = '/organizations/usage';

interface SidebarPlanRowProps {
  /** Licence edition from `GET /usage`, or `null` while it loads. */
  edition: string | null;
  /** Whether that licence is currently active. `null`/`undefined` when not
   * yet known — see `isUnlicensedPlan` in `utils/quota.ts`. */
  licensed?: boolean | null;
}

/**
 * The org's current plan, as the first row of the sidebar's footer card.
 *
 * Deliberately holds no opinion about the plan itself. Naming the edition,
 * marking a lapsed licence "inactive", and colouring a paid plan apart from a
 * free one are all :component:`PlanChip`'s job, and it already does them for
 * the usage page and the org-menu block. Re-deriving any of that here would
 * let the sidebar and the usage page disagree about the same licence.
 *
 * The layout mirrors the org-menu usage block in `Sidebar.tsx`, which pairs a
 * caption with the same chip — so the two plan readouts in this sidebar are
 * one pattern, not two.
 *
 * Renders nothing until `edition` is known: a plan must not flicker from a
 * placeholder to the real value.
 */
export function SidebarPlanRow({ edition, licensed }: SidebarPlanRowProps) {
  if (!edition) return null;

  return (
    <Box
      component={NextLink}
      href={USAGE_HREF}
      aria-label="Current plan — view usage"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        ...NAV_CARD_STATUS_ROW_SX,
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        // Separates status from the actions below it. The card draws no
        // dividers between its own links, so without this the plan reads as a
        // third thing you could click to do something.
        borderBottom: theme => `1px solid ${theme.palette.greyscale.border}`,
        '&:hover': {
          bgcolor: theme => theme.palette.greyscale.surface1,
        },
        transition: theme =>
          theme.transitions.create('background-color', {
            duration: theme.transitions.duration.shortest,
          }),
      }}
    >
      <Typography variant="caption">Plan</Typography>
      <PlanChip edition={edition} licensed={licensed} />
    </Box>
  );
}

export default SidebarPlanRow;
