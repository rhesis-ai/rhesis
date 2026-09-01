import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SidebarPlanRow } from '../SidebarPlanRow';

/**
 * The row's own job is placement and delegation: show up once the plan is
 * known, link to usage, and hand the edition and licence status to `PlanChip`.
 *
 * How a plan is *named* and *coloured* — the "(inactive)" marker, paid vs free
 * — belongs to `PlanChip` and is covered in `QuotaChips.test.tsx`. Asserting it
 * again here would duplicate that contract and make a deliberate copy change
 * fail in two places.
 */
describe('SidebarPlanRow', () => {
  it('renders nothing until the edition is known', () => {
    // A plan must not flicker from a placeholder to the real value.
    const { container } = render(<SidebarPlanRow edition={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('labels the row and links to the usage page', () => {
    render(<SidebarPlanRow edition="team" licensed={true} />);

    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      '/organizations/usage'
    );
  });

  it('shows the plan through PlanChip rather than its own label', () => {
    render(<SidebarPlanRow edition="Enterprise" licensed={true} />);

    // Lower-cased is PlanChip's formatting, which is the point: the row does
    // not format the edition itself.
    expect(screen.getByText('enterprise')).toBeInTheDocument();
  });

  it('passes licence status through, so a lapsed plan is marked', () => {
    // Not a re-test of the chip's copy -- it proves `licensed` actually reaches
    // it. Dropping the prop would leave a lapsed plan looking active here while
    // the usage page called it inactive.
    render(<SidebarPlanRow edition="enterprise" licensed={false} />);

    expect(screen.getByText('enterprise (inactive)')).toBeInTheDocument();
  });

  it('does not mark a plan inactive when licence status is unknown', () => {
    render(<SidebarPlanRow edition="enterprise" />);

    expect(screen.getByText('enterprise')).toBeInTheDocument();
    expect(screen.queryByText(/inactive/i)).not.toBeInTheDocument();
  });
});
