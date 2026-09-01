import {
  DEFAULT_PLAN_STYLE,
  isUpgradeable,
  planLabel,
  resolvePlanStyle,
} from '@/utils/plan';
import type { Plan } from '@/utils/api-client/features-client';

const plan = (over: Partial<Plan> = {}): Plan => ({
  name: 'Team',
  is_paid: true,
  is_active: true,
  ...over,
});

describe('resolvePlanStyle', () => {
  it('styles a free plan neutrally with an outlined crown', () => {
    const style = resolvePlanStyle(
      plan({ name: 'Community', is_paid: false, is_active: false })
    );
    expect(style.variant).toBe('free');
    expect(style.crownFilled).toBe(false);
    expect(style.crownColor).toBeNull();
  });

  it('gives an active paid plan a filled premium crown', () => {
    const style = resolvePlanStyle(plan());
    expect(style.variant).toBe('paid');
    expect(style.crownFilled).toBe(true);
    expect(style.crownColor).toBe('premium');
    expect(style.crownShadow).toBe(true);
  });

  it('lifts only an active paid crown off the surface', () => {
    // A shadow on the neutral crown would make a free plan look like it was
    // signalling something, which is the opposite of the intent.
    //
    // Asserted here rather than on the rendered icon because jsdom's cssstyle
    // does not implement `filter`: it is dropped from the emotion rule, so a
    // DOM assertion would pass whatever the component does.
    expect(resolvePlanStyle(plan()).crownShadow).toBe(true);
    for (const p of [
      plan({ is_paid: false, is_active: false }),
      plan({ is_active: false }),
      null,
      undefined,
    ]) {
      expect(resolvePlanStyle(p).crownShadow).toBe(false);
    }
  });

  it('does not dress a lapsed paid plan as paid', () => {
    // The backend holds this org to free-tier ceilings, so showing it a filled
    // premium crown would misreport what it can actually do. The distinction
    // rides on the label ("... (inactive)"), which the API composes.
    const style = resolvePlanStyle(plan({ is_active: false }));
    expect(style.variant).toBe('lapsed');
    expect(style.crownFilled).toBe(false);
    expect(style.crownColor).toBeNull();
  });

  it('varies nothing but the crown across tiers', () => {
    // The badge is neutral for every tier, so the resolver has no badge colour
    // to return. If one is ever added, the free tier ends up wearing the
    // loudest pill in the UI, which is what this guards.
    const free = resolvePlanStyle(plan({ is_paid: false, is_active: false }));
    const paid = resolvePlanStyle(plan());
    expect(Object.keys(free).sort()).toEqual([
      'crownColor',
      'crownFilled',
      'crownShadow',
      'variant',
    ]);
    expect(Object.keys(paid).sort()).toEqual(Object.keys(free).sort());
  });

  it('styles a tier it has never heard of by its flags, not its name', () => {
    // The whole point of the resolver's shape: a tier added on the backend
    // renders correctly with no frontend release. A resolver switching on
    // known names would have silently styled this as free.
    const style = resolvePlanStyle(
      plan({ name: 'Ultra Premium Plus', is_paid: true, is_active: true })
    );
    expect(style.variant).toBe('paid');
    expect(style.crownFilled).toBe(true);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
  ])('falls back to the neutral default for %s', (_label, value) => {
    expect(resolvePlanStyle(value)).toEqual(DEFAULT_PLAN_STYLE);
    expect(DEFAULT_PLAN_STYLE.variant).toBe('free');
  });

  it.each([
    ['missing flags', { name: 'Mystery' }],
    ['string flags', { name: 'Mystery', is_paid: 'yes', is_active: 'yes' }],
    ['null flags', { name: 'Mystery', is_paid: null, is_active: null }],
  ])('treats a malformed plan (%s) as free rather than paid', (_l, value) => {
    // Fail toward "no entitlement". Never render a paid style for a plan we
    // cannot confirm is paid, and never throw -- this runs in the protected
    // layout's sidebar, where a render error takes down every page.
    const style = resolvePlanStyle(value as unknown as Plan);
    expect(style.variant).toBe('free');
  });
});

describe('isUpgradeable', () => {
  it('offers an upgrade to a free org', () => {
    expect(isUpgradeable(plan({ is_paid: false, is_active: false }))).toBe(
      true
    );
  });

  it('offers one to a paid org whose licence lapsed', () => {
    expect(isUpgradeable(plan({ is_active: false }))).toBe(true);
  });

  it('does not offer one to an active paid org', () => {
    expect(isUpgradeable(plan())).toBe(false);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['missing is_active', { name: 'Team', is_paid: true }],
  ])('offers nothing when the plan is unknown (%s)', (_l, value) => {
    // Must not prompt a paying customer to upgrade on missing data.
    expect(isUpgradeable(value as unknown as Plan)).toBe(false);
  });
});

describe('planLabel', () => {
  it('returns the name exactly as the API sent it', () => {
    // No casing, mapping or suffixing. The API composes the whole label.
    for (const name of [
      'Community',
      'Enterprise (inactive)',
      'ULTRA',
      'très-premium',
    ]) {
      expect(planLabel(plan({ name }))).toBe(name);
    }
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['empty name', { name: '', is_paid: false, is_active: false }],
    ['blank name', { name: '   ', is_paid: false, is_active: false }],
  ])('returns null when there is nothing to show (%s)', (_l, value) => {
    expect(planLabel(value as unknown as Plan)).toBeNull();
  });
});
