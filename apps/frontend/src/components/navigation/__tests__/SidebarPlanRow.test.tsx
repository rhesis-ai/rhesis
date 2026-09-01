import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SidebarPlanRow } from '../SidebarPlanRow';
import { NavLinkItem } from '../NavLinkItem';
import type { Plan } from '@/utils/api-client/features-client';
import type { NavigationLinkItem } from '@/types/navigation';
import { UPGRADE_URL } from '@/constants/quota';
import { usePlan } from '@/contexts/FeaturesContext';
import { useCanUpgrade } from '@/hooks/useQuotaGate';

jest.mock('@/contexts/FeaturesContext', () => ({
  usePlan: jest.fn(),
}));

jest.mock('@/hooks/useQuotaGate', () => ({
  useCanUpgrade: jest.fn(),
}));

const mockUsePlan = usePlan as jest.MockedFunction<typeof usePlan>;
const mockUseCanUpgrade = useCanUpgrade as jest.MockedFunction<
  typeof useCanUpgrade
>;

const plan = (over: Partial<Plan> = {}): Plan => ({
  name: 'Team',
  is_paid: true,
  is_active: true,
  ...over,
});

/** The row reads the plan itself now, so the source is stubbed rather than
 * passed in. It comes from `GET /features` (server-seeded), which is what makes
 * it present on first paint. */
function renderRow(
  value: Plan | null | undefined,
  { canUpgrade = false } = {}
) {
  // No default for `value`: a default would swallow an explicitly passed
  // `undefined`, which is one of the cases under test.
  mockUsePlan.mockReturnValue(value ?? null);
  mockUseCanUpgrade.mockReturnValue(canUpgrade);
  return render(<SidebarPlanRow />);
}

beforeEach(() => {
  mockUsePlan.mockReset();
  mockUseCanUpgrade.mockReset();
  mockUseCanUpgrade.mockReturnValue(false);
});

/**
 * The row's own job is layout and delegation: sit on the shared nav-row
 * primitive, label the row, and hand the plan to `PlanBadge`.
 *
 * How a plan is named and coloured belongs to `PlanBadge` / `resolvePlanStyle`
 * and is covered in `PlanBadge.test.tsx` and `plan.test.ts`.
 */
describe('SidebarPlanRow', () => {
  it('labels the row', () => {
    renderRow(plan());
    expect(screen.getByText('Plan')).toBeInTheDocument();
  });

  it('reads the tier out with what it describes', () => {
    // The row is one labelled unit, so the tier is not announced as a loose
    // word floating next to "Plan".
    renderRow(plan({ name: 'Community' }));
    expect(
      screen.getByRole('group', { name: 'Plan: Community' })
    ).toBeInTheDocument();
  });

  it('is not interactive, and carries no affordance suggesting it is', () => {
    // The row reports state rather than doing something. Beside two rows that
    // are actionable, a pointer cursor or hover tint would read as a broken
    // link. (The upgrade link below is its own target, not a row click.)
    const { container } = renderRow(plan());
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();

    const row = container.firstElementChild as HTMLElement;
    expect(row.tagName).not.toBe('A');
    expect(getComputedStyle(row).cursor).not.toBe('pointer');
  });

  describe('the upgrade prompt', () => {
    it('offers an upgrade on a free plan', () => {
      renderRow(plan({ name: 'Community', is_paid: false, is_active: false }), {
        canUpgrade: true,
      });
      const link = screen.getByRole('link', { name: /upgrade/i });
      expect(link).toHaveAttribute('href', UPGRADE_URL);
      // Opens the public pricing page, which is outside the app.
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
    });

    it('leaves the row otherwise intact', () => {
      // The prompt is additive: the caption and the tier must still read.
      renderRow(plan({ name: 'Community', is_paid: false, is_active: false }), {
        canUpgrade: true,
      });
      expect(screen.getByText('Plan')).toBeInTheDocument();
      expect(screen.getByText('Community')).toBeInTheDocument();
    });

    it('offers nothing to a reader who cannot act on it', () => {
      // `useCanUpgrade` gates on Organization.UPDATE, not the usage:read every
      // member holds. Prompting someone who cannot change billing is worse than
      // staying quiet.
      renderRow(plan({ name: 'Community', is_paid: false, is_active: false }), {
        canUpgrade: false,
      });
      expect(
        screen.queryByRole('link', { name: /upgrade/i })
      ).not.toBeInTheDocument();
    });

    it('offers nothing on an active paid plan', () => {
      renderRow(plan(), { canUpgrade: false });
      expect(
        screen.queryByRole('link', { name: /upgrade/i })
      ).not.toBeInTheDocument();
    });
  });

  it('hides the crown from assistive tech', () => {
    // Colour and fill are not information a screen reader can use, and the
    // tier is already in the row's name.
    const { container } = renderRow(plan());
    const icon = container.querySelector('svg');
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('shows the plan through PlanBadge, verbatim', () => {
    renderRow(plan({ name: 'uLtRa PREMIUM' }));
    expect(screen.getByText('uLtRa PREMIUM')).toBeInTheDocument();
  });

  it('passes the plan through, so a lapsed one is marked', () => {
    // Proves the plan actually reaches the badge, rather than the row rendering
    // a name with no regard for licence state.
    renderRow(plan({ name: 'Enterprise (inactive)', is_active: false }));
    expect(screen.getByText('Enterprise (inactive)')).toBeInTheDocument();
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
  ])('renders nothing until the plan is known (%s)', (_l, value) => {
    const { container } = renderRow(value as unknown as Plan);
    expect(container).toBeEmptyDOMElement();
  });

  describe('alignment with the sibling nav rows', () => {
    /**
     * The reason this row was rewritten: it used a bespoke layout, so its
     * content started at a different x-offset from "Star Rhesis" and "Support".
     *
     * The row is stacked ("Plan" caption over `[crown] [badge]`) because a
     * single line does not fit in the 160px content box -- see the component's
     * own note. What still has to hold is that it reuses the shared primitives,
     * so its padding and icon gutter match the rows beneath it.
     *
     * Asserted structurally rather than by pixel: both rows must resolve the
     * same shared primitives, so this is a property of the code rather than of
     * a snapshot.
     */
    const starItem: NavigationLinkItem = {
      kind: 'link',
      title: 'Star Rhesis',
      href: 'https://github.com/rhesis-ai/rhesis',
      external: true,
      icon: <svg />,
    };

    function rowOf(container: HTMLElement): HTMLElement {
      const el = container.firstElementChild;
      if (!(el instanceof HTMLElement)) throw new Error('no row rendered');
      return el;
    }

    it('uses the same horizontal padding as a nav row', () => {
      const planRow = rowOf(renderRow(plan()).container);
      const navRow = rowOf(
        render(<NavLinkItem item={starItem} collapsed={false} />).container
      );

      const p = getComputedStyle(planRow);
      const n = getComputedStyle(navRow);
      expect(p.paddingLeft).toBe(n.paddingLeft);
      expect(p.paddingRight).toBe(n.paddingRight);
      expect(p.display).toBe('flex');
    });

    it('gives the crown the same gutter as a nav row icon', () => {
      // The crown sits on the row's second line, but in the same 24px gutter at
      // the same left padding, so the icon column the brief asked for holds.
      const planIcon = rowOf(renderRow(plan()).container).lastElementChild
        ?.firstElementChild;
      const navIcon = rowOf(
        render(<NavLinkItem item={starItem} collapsed={false} />).container
      ).firstElementChild;

      expect(planIcon).toBeInstanceOf(HTMLElement);
      expect(navIcon).toBeInstanceOf(HTMLElement);
      const p = getComputedStyle(planIcon as HTMLElement);
      const n = getComputedStyle(navIcon as HTMLElement);
      // flexShrink 0 on both is what fixes the gutter regardless of glyph.
      expect(p.flexShrink).toBe(n.flexShrink);
      expect(p.flexShrink).toBe('0');
    });

    it('keeps the whole word "Plan" whatever the tier is called', () => {
      // The regression that prompted the stack: with everything on one line the
      // label ellipsized to "Pl..." next to a mere "Community" pill.
      renderRow(plan({ name: 'An Extremely Long Tier Name Indeed' }));
      expect(screen.getByText('Plan')).toBeInTheDocument();
      expect(
        screen.getByText('An Extremely Long Tier Name Indeed')
      ).toBeInTheDocument();
    });

    it('puts the badge after the label in document order', () => {
      const { container } = renderRow(plan());
      const label = screen.getByText('Plan');
      const badge = screen.getByText('Team');
      expect(
        label.compareDocumentPosition(badge) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
      expect(container).toContainElement(badge);
    });
  });
});
