/**
 * The single plan→style resolver.
 *
 * Every surface that displays a plan — the sidebar footer row, the sidebar
 * org menu, the usage page, and anything added later — renders `PlanBadge`
 * and gets its styling from here. One resolver, one badge, so two surfaces
 * can never disagree about what a plan looks like.
 *
 * **It never looks at the plan's name.** Styling is decided entirely by the
 * two booleans the API supplies (`is_paid`, `is_active`), which is what makes
 * a renamed or newly added tier render correctly with no frontend release. A
 * resolver that switched on `"community"` / `"enterprise"` would silently
 * style an unknown tier as free — the failure this shape exists to prevent.
 *
 * `Plan` is deliberately not a union of known tiers. There is no client-side
 * list of tiers to fall out of date.
 */

import type { Plan } from '@/utils/api-client/features-client';

/**
 * Which of the three presentation states a plan is in.
 *
 * Derived, not transmitted: the API sends orthogonal facts (`is_paid`,
 * `is_active`) and this collapses them into the one axis styling varies on.
 *
 * - `free` — not a paid tier. Neutral; nothing to celebrate, nothing wrong.
 * - `paid` — a paid tier with an active licence. Filled premium crown.
 * - `lapsed` — a paid tier whose licence is no longer active. The state an
 *   admin needs to notice, because the backend is holding them to free-tier
 *   ceilings while their plan still names the tier they bought.
 */
export type PlanVariant = 'free' | 'paid' | 'lapsed';

export interface PlanStyle {
  variant: PlanVariant;
  /** Whether the crown is drawn filled (an earned state) or outlined. */
  crownFilled: boolean;
  /**
   * Palette key for the crown, or `null` to inherit the row's icon colour.
   *
   * Spelled out rather than `keyof typeof PLAN_COLORS.light`, which would also
   * admit `premiumShadow` — a shadow is not a crown colour.
   *
   * The crown is the **only** element whose colour varies by tier. The badge is
   * neutral for every tier, so the free tier never ends up wearing the most
   * saturated pill in the UI — and a paid plan is marked by the crown rather
   * than by a louder badge.
   */
  crownColor: 'premium' | null;
  /**
   * Whether the crown is lifted off the surface with a drop shadow.
   *
   * Lives here rather than being inferred in the component, so "what does this
   * tier look like" stays one decision in one place. Only an active paid plan
   * glows: a shadow on the neutral crown would make a free plan look like it
   * was signalling something.
   */
  crownShadow: boolean;
}

/**
 * The variant table. Keyed on the boolean pair rather than on tier names, so
 * adding a tier requires no entry here.
 *
 * `free` is the safe default: an unknown, missing or malformed plan renders as
 * a neutral badge with an outlined crown. It must never crash, render blank, or
 * be styled as a paid plan the org has not got.
 */
const STYLES: Record<PlanVariant, PlanStyle> = {
  free: {
    variant: 'free',
    crownFilled: false,
    crownColor: null,
    crownShadow: false,
  },
  paid: {
    variant: 'paid',
    crownFilled: true,
    crownColor: 'premium',
    crownShadow: true,
  },
  // Styled identically to `free`, and honestly so: a lapsed licence is held to
  // free-tier ceilings, so presenting it as paid would misreport what the org
  // can actually do. The distinction is carried by the label, which the API
  // composes with its "(inactive)" qualifier -- text, not colour, which is also
  // what keeps it legible in a monochrome theme. The variant stays separate
  // because `isUpgradeable` needs it.
  lapsed: {
    variant: 'lapsed',
    crownFilled: false,
    crownColor: null,
    crownShadow: false,
  },
};

/** The neutral fallback, exported so callers can render before a plan loads. */
export const DEFAULT_PLAN_STYLE: PlanStyle = STYLES.free;

/**
 * Resolve *plan* to its style tokens.
 *
 * Accepts `null`/`undefined` and anything structurally unexpected, returning
 * the neutral default rather than throwing: this runs in the protected layout's
 * sidebar, where a render error takes down every page rather than one badge.
 */
export function resolvePlanStyle(plan: Plan | null | undefined): PlanStyle {
  if (!plan || typeof plan !== 'object') return DEFAULT_PLAN_STYLE;
  if (plan.is_paid !== true) return STYLES.free;
  return plan.is_active === true ? STYLES.paid : STYLES.lapsed;
}

/**
 * Whether this org should be offered an upgrade path.
 *
 * True for a free org and for a paid org whose licence has lapsed — both are
 * held to free-tier ceilings, and the lapsed one is the case that most needs
 * the prompt. Requires a positive `false` on `is_active`, so a plan that has
 * not loaded yet shows nothing rather than prompting a paying customer.
 */
export function isUpgradeable(plan: Plan | null | undefined): boolean {
  if (!plan || typeof plan !== 'object') return false;
  return plan.is_active === false;
}

/**
 * The plan's display label, or `null` when there is nothing to show yet.
 *
 * Returned verbatim. No casing, mapping or suffixing — the API composes the
 * full label, qualifier included, precisely so this stays a passthrough.
 */
export function planLabel(plan: Plan | null | undefined): string | null {
  if (!plan || typeof plan !== 'object') return null;
  const name = plan.name;
  return typeof name === 'string' && name.trim() !== '' ? name : null;
}
