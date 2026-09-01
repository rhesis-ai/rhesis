'use client';

import Chip from '@mui/material/Chip';
import { useTheme } from '@mui/material/styles';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import WorkspacePremiumOutlinedIcon from '@mui/icons-material/WorkspacePremiumOutlined';
import { BORDER_RADIUS, PLAN_COLORS } from '@/styles/theme-constants';
import { planLabel, resolvePlanStyle } from '@/utils/plan';
import type { Plan } from '@/utils/api-client/usage-client';

/**
 * The plan pill. **The only one.** Every surface that shows a plan renders
 * this and takes its styling from `resolvePlanStyle`, so the sidebar, the org
 * menu and the usage page cannot drift apart.
 *
 * Every variant gets identical padding, radius, size and weight from the one
 * `Chip` below — only the colour differs, and only because the resolver
 * returned a different value. Two tiers can never differ in size or shape.
 *
 * The label is whatever the API sent, rendered verbatim. Nothing here maps,
 * cases or inspects a tier name, so an unrecognized tier displays correctly
 * with no code change and falls back to the neutral style.
 *
 * Renders nothing when there is no plan yet, rather than a placeholder: a plan
 * must not flicker from a guess to the real value.
 */
export function PlanBadge({ plan }: { plan: Plan | null | undefined }) {
  const label = planLabel(plan);
  if (label === null) return null;

  return (
    <Chip
      label={label}
      size="small"
      color={resolvePlanStyle(plan).chipColor}
      sx={{
        borderRadius: BORDER_RADIUS.pill,
        // Read from the theme rather than written as 600: the semibold weight
        // is brand-dependent (`w600` in theme.ts is 700 when a brand font is
        // configured), so a literal would render this badge lighter than every
        // other semibold element on a branded deployment.
        fontWeight: theme => theme.typography.captionBold.fontWeight,
      }}
    />
  );
}

/**
 * The plan's crown, for a row that leads with an icon.
 *
 * Filled and gold for an active paid plan; outlined otherwise. Kept beside the
 * badge so the crown and the pill are resolved from the same place — the icon
 * and the pill disagreeing about whether a plan is paid would be worse than
 * either being wrong alone.
 *
 * Takes no colour prop. A caller wanting the neutral row colour gets it by
 * default, because the resolver returns `crownColor: null` for the free
 * variant and this then inherits.
 */
export function PlanCrownIcon({ plan }: { plan: Plan | null | undefined }) {
  const theme = useTheme();
  const style = resolvePlanStyle(plan);
  const Icon = style.crownFilled
    ? WorkspacePremiumIcon
    : WorkspacePremiumOutlinedIcon;

  const palette =
    theme.palette.mode === 'dark' ? PLAN_COLORS.dark : PLAN_COLORS.light;
  const color =
    style.crownColor === null
      ? 'inherit'
      : style.crownColor === 'warning'
        ? theme.palette.warning.main
        : palette[style.crownColor];

  return <Icon sx={{ color }} />;
}

export default PlanBadge;
