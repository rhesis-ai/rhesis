import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { GridBadge } from '@/components/common/GridBadge';
import { PlanBadge, PlanCrownIcon } from '@/components/common/PlanBadge';
import type { Plan } from '@/utils/api-client/features-client';

const plan = (over: Partial<Plan> = {}): Plan => ({
  name: 'Team',
  is_paid: true,
  is_active: true,
  ...over,
});

/** MUI stamps each icon with its own name — the stable way to assert
 * filled-vs-outlined without reading computed styles. */
const FILLED = 'CrownFilledIcon';
const OUTLINED = 'CrownOutlinedIcon';

/** The visual properties that must not vary: by tier, or from the app's own
 * badge. Deliberately includes colour, which is where the drift was. */
function snapshotOf(el: HTMLElement): string {
  const cs = getComputedStyle(el);
  return [
    cs.backgroundColor,
    cs.color,
    cs.borderRadius,
    cs.fontSize,
    cs.fontWeight,
    cs.lineHeight,
    cs.paddingLeft,
    cs.paddingRight,
    cs.textTransform,
  ].join('|');
}

describe('PlanBadge', () => {
  it('renders the API name verbatim', () => {
    // Deliberately awkward casing: nothing may normalize it.
    render(<PlanBadge plan={plan({ name: 'uLtRa PREMIUM' })} />);
    expect(screen.getByText('uLtRa PREMIUM')).toBeInTheDocument();
  });

  it('renders a lapsed plan with the qualifier the API supplied', () => {
    render(
      <PlanBadge
        plan={plan({ name: 'Enterprise (inactive)', is_active: false })}
      />
    );
    expect(screen.getByText('Enterprise (inactive)')).toBeInTheDocument();
  });

  it('renders a tier it has never heard of', () => {
    const { container } = render(
      <PlanBadge plan={plan({ name: 'Brand New Tier' })} />
    );
    expect(screen.getByText('Brand New Tier')).toBeInTheDocument();
    expect(container).not.toBeEmptyDOMElement();
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['blank name', { name: '  ', is_paid: false, is_active: false }],
  ])('renders nothing when there is no plan (%s)', (_l, value) => {
    // Not a placeholder: a plan must not flicker from a guess to the truth.
    const { container } = render(<PlanBadge plan={value as unknown as Plan} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('is the same pill as every other badge in the app', () => {
    // The plan is org metadata, which is what `GridBadge` is for. Styling it
    // separately made it look *almost* like the app's other badges, which
    // reads as a mistake rather than as a distinction.
    const planRender = render(<PlanBadge plan={plan()} />);
    const planPill = planRender.container.firstElementChild as HTMLElement;
    const planStyle = snapshotOf(planPill);
    planRender.unmount();

    const refRender = render(<GridBadge label="Team" size="grid" />);
    const refPill = refRender.container.firstElementChild as HTMLElement;
    const refStyle = snapshotOf(refPill);
    refRender.unmount();

    expect(planStyle).toBe(refStyle);
  });

  it('gives every tier an identical pill, colour included', () => {
    // The badge must not vary by tier at all -- not in size, radius, type or
    // colour. Only the crown varies. Without this, the free tier ends up
    // wearing the most saturated pill in the UI.
    const styles = (
      [
        plan({ is_paid: false, is_active: false }),
        plan(),
        plan({ is_active: false }),
        plan({ name: 'Never Heard Of It' }),
      ] as Plan[]
    ).map(p => {
      const { container, unmount } = render(<PlanBadge plan={p} />);
      const snapshot = snapshotOf(container.firstElementChild as HTMLElement);
      unmount();
      return snapshot;
    });
    expect(new Set(styles).size).toBe(1);
  });
});

describe('PlanCrownIcon', () => {
  it('fills the crown for an active paid plan', () => {
    const { container } = render(<PlanCrownIcon plan={plan()} />);
    expect(
      container.querySelector(`[data-testid="${FILLED}"]`)
    ).toBeInTheDocument();
  });

  it('outlines the crown for a free plan', () => {
    const { container } = render(
      <PlanCrownIcon plan={plan({ is_paid: false, is_active: false })} />
    );
    expect(
      container.querySelector(`[data-testid="${OUTLINED}"]`)
    ).toBeInTheDocument();
  });

  it('outlines the crown for a lapsed plan', () => {
    const { container } = render(
      <PlanCrownIcon plan={plan({ is_active: false })} />
    );
    expect(
      container.querySelector(`[data-testid="${OUTLINED}"]`)
    ).toBeInTheDocument();
  });

  it('still renders a crown for an unknown plan rather than crashing', () => {
    const { container } = render(<PlanCrownIcon plan={null} />);
    expect(
      container.querySelector(`[data-testid="${OUTLINED}"]`)
    ).toBeInTheDocument();
  });
});
