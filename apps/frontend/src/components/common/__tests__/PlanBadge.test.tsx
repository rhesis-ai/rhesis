import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
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
const FILLED = 'WorkspacePremiumIcon';
const OUTLINED = 'WorkspacePremiumOutlinedIcon';

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

  it('gives every variant the same shape, differing only in colour', () => {
    // Two tiers must never differ in size or radius. One Chip, one set of sx.
    const shapes = (
      [
        plan({ is_paid: false, is_active: false }),
        plan(),
        plan({ is_active: false }),
      ] as Plan[]
    ).map(p => {
      const { container, unmount } = render(<PlanBadge plan={p} />);
      const chip = container.querySelector('.MuiChip-root');
      const cls = chip?.className ?? '';
      // Size class is what encodes padding/height; colour classes are excluded.
      const size = /MuiChip-size\w+/.exec(cls)?.[0] ?? '';
      unmount();
      return size;
    });
    expect(new Set(shapes).size).toBe(1);
    expect(shapes[0]).toBe('MuiChip-sizeSmall');
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
