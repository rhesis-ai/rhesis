'use client';

import { useTheme } from '@mui/material/styles';
import {
  CrownFilledIcon,
  CrownOutlinedIcon,
} from '@/components/common/CrownIcon';
import { GridBadge } from '@/components/common/GridBadge';
import { PLAN_COLORS, PLAN_CROWN_SHADOW } from '@/styles/theme-constants';
import { planLabel, resolvePlanStyle } from '@/utils/plan';
import type { Plan } from '@/utils/api-client/features-client';

/**
 * The plan pill. **The only one.** Every surface that shows a plan renders
 * this, so the sidebar footer, the sidebar org menu and the usage page cannot
 * drift apart.
 *
 * It is a thin wrapper over `GridBadge`, the app's read-only pill, rather than
 * its own styled chip. That is deliberate: the plan is metadata about the org,
 * which is exactly what `GridBadge` is for (`Tag`'s docstring routes badges
 * here), so the plan pill picks up the same grey fill, pill radius, type and
 * padding as every other badge in the app. A bespoke chip here looked
 * *almost* like the app's badges, which is worse than either matching or
 * clearly differing.
 *
 * No `size` passthrough, so the plan reads identically on all three surfaces.
 * Nothing about the badge varies by tier either — same fill, radius, type and
 * casing for every plan. Paid-ness is signalled by the crown, which keeps the
 * free tier from wearing the loudest pill in the UI.
 *
 * The label is whatever the API sent, rendered verbatim. Nothing here maps,
 * cases or inspects a tier name, so an unrecognized tier displays correctly
 * with no code change.
 *
 * Renders nothing when there is no plan yet, rather than a placeholder: a plan
 * must not flicker from a guess to the real value.
 */
export function PlanBadge({ plan }: { plan: Plan | null | undefined }) {
  const label = planLabel(plan);
  if (label === null) return null;

  return <GridBadge label={label} size="grid" />;
}

/**
 * The plan's crown, for a row that leads with an icon.
 *
 * Filled and premium-gold for an active paid plan; outlined otherwise. Kept beside the
 * badge so the crown and the pill are resolved from the same place — the icon
 * and the pill disagreeing about whether a plan is paid would be worse than
 * either being wrong alone.
 *
 * Takes no colour prop. The resolver returns `crownColor: null` for anything
 * not actively paid, which inherits, so a free plan's crown is the same colour
 * as the other icons in the card. Only an active paid plan colours itself.
 */
export function PlanCrownIcon({ plan }: { plan: Plan | null | undefined }) {
  const theme = useTheme();
  const style = resolvePlanStyle(plan);
  const Icon = style.crownFilled ? CrownFilledIcon : CrownOutlinedIcon;

  const isDark = theme.palette.mode === 'dark';
  const palette = isDark ? PLAN_COLORS.dark : PLAN_COLORS.light;
  // `inherit` rather than a token of its own: the caller sets the row's icon
  // colour, so a non-paid crown matches the sibling nav icons ("Star Rhesis",
  // "Support") exactly. Naming a secondary token here made it visibly lighter
  // than the icons beside it.
  const color = style.crownColor === null ? 'inherit' : palette.premium;

  // Decorative: the tier is already carried by the badge text, and the
  // filled-vs-outlined shape is the non-colour second channel. Announcing the
  // icon too would just repeat the row.
  return (
    <Icon
      aria-hidden="true"
      sx={{
        color,
        // Only the active paid crown is lifted off the surface. A glow on the
        // neutral crown would make a free plan look like it was signalling
        // something, which is the opposite of the intent. The recipe itself is
        // a token -- see PLAN_CROWN_SHADOW for why it is two chained shadows.
        ...(style.crownShadow
          ? {
              filter: isDark ? PLAN_CROWN_SHADOW.dark : PLAN_CROWN_SHADOW.light,
            }
          : {}),
      }}
    />
  );
}

export default PlanBadge;
