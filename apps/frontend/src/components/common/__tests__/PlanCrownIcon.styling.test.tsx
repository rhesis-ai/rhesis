/**
 * What `PlanCrownIcon` actually hands to the icon.
 *
 * Separate from `PlanBadge.test.tsx` because it mocks `CrownIcon` to capture the
 * props, which would defeat that file's filled-vs-outlined assertions.
 *
 * This exists because the premium styling is otherwise unverifiable: jsdom's
 * cssstyle does not implement `filter`, so it is dropped from the emotion rule
 * and neither `getComputedStyle` nor the injected CSS can see it. A `filter`
 * assertion through the DOM passes whatever the component does — which is how a
 * dropped edit shipped with the crown rendering gold but flat, and only a human
 * looking at the sidebar caught it. Capturing the props is the one seam that
 * fails when the wiring is missing.
 */

import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PlanCrownIcon } from '@/components/common/PlanBadge';
import {
  CrownFilledIcon,
  CrownOutlinedIcon,
} from '@/components/common/CrownIcon';
import { PLAN_COLORS, PLAN_CROWN_SHADOW } from '@/styles/theme-constants';
import type { Plan } from '@/utils/api-client/features-client';

jest.mock('@/components/common/CrownIcon', () => ({
  CrownFilledIcon: jest.fn(() => null),
  CrownOutlinedIcon: jest.fn(() => null),
}));

const filled = CrownFilledIcon as jest.Mock;
const outlined = CrownOutlinedIcon as jest.Mock;

const plan = (over: Partial<Plan> = {}): Plan => ({
  name: 'Team',
  is_paid: true,
  is_active: true,
  ...over,
});

/** The `sx` the rendered icon received. */
function sxOf(mock: jest.Mock): Record<string, unknown> {
  expect(mock).toHaveBeenCalled();
  return mock.mock.calls[0][0].sx as Record<string, unknown>;
}

beforeEach(() => {
  filled.mockClear();
  outlined.mockClear();
});

describe('PlanCrownIcon styling', () => {
  it('lifts an active paid crown with a drop shadow', () => {
    render(<PlanCrownIcon plan={plan()} />);
    const sx = sxOf(filled);
    expect(String(sx.filter)).toContain('drop-shadow');
    // Both layers: the contact shadow seats it, the halo makes it glow. One
    // alone is invisible at 24px.
    expect(String(sx.filter).match(/drop-shadow/g)).toHaveLength(2);
  });

  it('paints the paid crown in the premium token, not an ad-hoc colour', () => {
    render(<PlanCrownIcon plan={plan()} />);
    // Default MUI theme is light in tests.
    expect(sxOf(filled).color).toBe(PLAN_COLORS.light.premium);
  });

  it('uses the shadow token verbatim, not a locally built filter', () => {
    render(<PlanCrownIcon plan={plan()} />);
    expect(sxOf(filled).filter).toBe(PLAN_CROWN_SHADOW.light);
  });

  it.each([
    ['free', plan({ is_paid: false, is_active: false })],
    ['lapsed', plan({ is_active: false })],
  ])('leaves the %s crown flat and inheriting', (_label, p) => {
    render(<PlanCrownIcon plan={p} />);
    const sx = sxOf(outlined);
    expect(sx.filter).toBeUndefined();
    expect(sx.color).toBe('inherit');
  });
});
