import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SidebarPlanRow } from '../SidebarPlanRow';
import { NavLinkItem } from '../NavLinkItem';
import type { Plan } from '@/utils/api-client/usage-client';
import type { NavigationLinkItem } from '@/types/navigation';

const plan = (over: Partial<Plan> = {}): Plan => ({
  name: 'Team',
  is_paid: true,
  is_active: true,
  ...over,
});

/**
 * The row's own job is layout and delegation: sit on the shared nav-row
 * primitive, label the row, and hand the plan to `PlanBadge`.
 *
 * How a plan is named and coloured belongs to `PlanBadge` / `resolvePlanStyle`
 * and is covered in `PlanBadge.test.tsx` and `plan.test.ts`.
 */
describe('SidebarPlanRow', () => {
  it('labels the row and links to the usage page', () => {
    render(<SidebarPlanRow plan={plan()} />);
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      '/organizations/usage'
    );
  });

  it('shows the plan through PlanBadge, verbatim', () => {
    render(<SidebarPlanRow plan={plan({ name: 'uLtRa PREMIUM' })} />);
    expect(screen.getByText('uLtRa PREMIUM')).toBeInTheDocument();
  });

  it('passes the plan through, so a lapsed one is marked', () => {
    // Proves `plan` actually reaches the badge. Dropping the prop would leave
    // the sidebar showing a lapsed plan as active while the usage page did not.
    render(
      <SidebarPlanRow
        plan={plan({ name: 'Enterprise (inactive)', is_active: false })}
      />
    );
    expect(screen.getByText('Enterprise (inactive)')).toBeInTheDocument();
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
  ])('renders nothing until the plan is known (%s)', (_l, value) => {
    const { container } = render(
      <SidebarPlanRow plan={value as unknown as Plan} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  describe('alignment with the sibling nav rows', () => {
    /**
     * The reason this row was rewritten: it used a bespoke layout, so its text
     * started at a different x-offset from "Star Rhesis" and "Support" and the
     * pill had no fixed anchor.
     *
     * Asserted structurally rather than by pixel: both rows must resolve the
     * same shared primitives, so identical horizontal padding and icon-gutter
     * width is a property of the code, not of a snapshot.
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
      const planRow = rowOf(render(<SidebarPlanRow plan={plan()} />).container);
      const navRow = rowOf(
        render(<NavLinkItem item={starItem} collapsed={false} />).container
      );

      const p = getComputedStyle(planRow);
      const n = getComputedStyle(navRow);
      expect(p.paddingLeft).toBe(n.paddingLeft);
      expect(p.paddingRight).toBe(n.paddingRight);
      expect(p.display).toBe('flex');
      expect(p.alignItems).toBe('center');
    });

    it('gives the icon gutter the same width, so labels share an x-offset', () => {
      const planIcon = rowOf(
        render(<SidebarPlanRow plan={plan()} />).container
      ).firstElementChild;
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

    it('anchors the badge right and protects it from a long tier name', () => {
      const { container } = render(
        <SidebarPlanRow
          plan={plan({ name: 'An Extremely Long Tier Name Indeed' })}
        />
      );
      const row = rowOf(container);
      const trailing = row.lastElementChild;
      expect(trailing).toBeInstanceOf(HTMLElement);

      const t = getComputedStyle(trailing as HTMLElement);
      // marginLeft:auto is the anchor; flexShrink:0 stops the badge compressing.
      expect(t.marginLeft).toBe('auto');
      expect(t.flexShrink).toBe('0');

      // The label yields instead, so the badge keeps its size. jsdom
      // normalizes a zero length to a bare "0", hence not comparing to "0px".
      const label = row.children[1];
      expect(parseFloat(getComputedStyle(label as HTMLElement).minWidth)).toBe(
        0
      );
    });

    it('puts the badge after the label in document order', () => {
      const { container } = render(<SidebarPlanRow plan={plan()} />);
      const label = screen.getByText('Plan');
      const badge = screen.getByText('Team');
      expect(
        label.compareDocumentPosition(badge) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
      expect(container).toContainElement(badge);
    });
  });
});
