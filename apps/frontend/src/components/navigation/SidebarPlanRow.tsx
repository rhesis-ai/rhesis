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

/**
 * The org's plan, as the first row of the sidebar's footer card.
 *
 * **The row itself is not interactive.** It reports state, so it takes
 * `interactive: false` from the shared row shell, dropping the pointer cursor
 * and hover tint that "Star Rhesis" and "Support" below it carry — without
 * those it would read as a broken link sitting next to two working ones. The
 * one control it can contain is the upgrade link below, which is its own
 * focusable target rather than a click on the whole row.
 *
 * The upgrade link shows only when there is something to upgrade *and* the
 * reader can act on it: `useCanUpgrade` gates on `Organization.UPDATE`, the same
 * owner/admin check the org menu's upgrade link uses, not on `usage:read` which
 * every member holds. Offering it to someone who cannot change billing is worse
 * than not offering it. It covers a lapsed paid plan too, not just the free
 * tier — that org is being held to free-tier ceilings and most needs the prompt.
 *
 * Built from the same row primitives as `NavLinkItem` — `navCardRowSx`,
 * `navCardIconSx`, `NAV_CARD_ICON_GAP` — rather than its own geometry, so the
 * padding and icon gutter cannot drift from the rows beneath it.
 *
 * Structure: a `Plan  Upgrade →` caption line, then `[crown] [tier badge]`
 * beneath it. The upgrade link follows the caption directly rather than being
 * pinned to the right edge, so the two read as one group; the caption line has
 * ~135px spare once "Plan" is drawn, where the badge line has only ~46px.
 *
 * Stacked rather than one line, because one line does not fit. The sidebar is
 * 240px with 26px of padding, so this card is 188px and the row's content box
 * is 160px. A single line needs 24px of crown, two 10px gaps, ~32px for the
 * word "Plan" and ~80px for a "Community" pill: 156px, leaving 4px. "Enterprise"
 * overflows outright, and "Enterprise (inactive)" is not close. The observed
 * symptom was the label ellipsizing to "Pl...".
 *
 * The crown still sits in the same 24px gutter at the same left padding as
 * "Star Rhesis" and "Support", so the icon column the brief asked for is
 * preserved; it is the label that moved, not the alignment.
 *
 * Holds no opinion about the plan itself. Naming the tier, deciding whether it
 * is paid, and colouring the crown are `PlanBadge` / `resolvePlanStyle`'s job,
 * driven off the API's booleans. Nothing here inspects a tier name, so a new
 * tier needs no change to this file.
 *
 * Renders nothing until the plan is known, rather than defaulting to a tier —
 * a plan must not flicker from a guess to the real value. In practice it is
 * known on first paint: `usePlan()` reads `GET /features`, which the protected
 * layout server-seeds.
 */
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
        // Stacked, so the tier name gets the row's full width. See the note on
        // the component above for why the single-line version cannot fit.
        flexDirection: 'column',
        alignItems: 'stretch',
        // Separates status from the actions below it. The card draws no
        // dividers between its own links, so without this the plan reads as a
        // third thing you could click to do something.
        borderBottom: (theme: Theme) =>
          `1px solid ${theme.palette.greyscale.border}`,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          // Same gap the rows below put between icon and label, so the caption
          // line reads as one left-aligned group rather than two things pinned
          // to opposite edges.
          gap: NAV_CARD_ICON_GAP,
        }}
      >
        <Typography
          variant="caption"
          sx={{ color: (theme: Theme) => theme.palette.greyscale.subtitle }}
        >
          Plan
        </Typography>

        {canUpgrade && (
          <MuiLink
            href={UPGRADE_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="caption"
            sx={{
              // From the theme, not the literal 700 the org menu's copy of this
              // link uses: the semibold weight is brand-dependent.
              fontWeight: (theme: Theme) =>
                theme.typography.captionBold.fontWeight,
            }}
          >
            Upgrade →
          </MuiLink>
        )}
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          // Same gap as a nav row's icon-to-label gap, so the badge starts on
          // the same x as "Star Rhesis" and "Support" do.
          gap: NAV_CARD_ICON_GAP,
        }}
      >
        <Box
          sx={{
            ...navCardIconSx,
            // Only applies to the free/lapsed crown, which returns no colour of
            // its own; the paid crown sets the premium token and wins.
            color: (theme: Theme) => theme.palette.greyscale.body,
          }}
        >
          <PlanCrownIcon plan={plan} />
        </Box>

        <PlanBadge plan={plan} />
      </Box>
    </Box>
  );
}

export default SidebarPlanRow;
