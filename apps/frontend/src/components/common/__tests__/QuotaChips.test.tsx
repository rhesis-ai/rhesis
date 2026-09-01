import { render, screen } from '@testing-library/react';
import { PlanChip, UpgradeLink } from '@/components/common/QuotaChips';
import { UPGRADE_URL } from '@/constants/quota';

describe('PlanChip', () => {
  it('names the plan in lower case', () => {
    render(<PlanChip edition="Enterprise" licensed={true} />);
    expect(screen.getByText('enterprise')).toBeInTheDocument();
  });

  it('marks a lapsed paid plan inactive', () => {
    // The backend keeps reporting the old edition for a canceled licence while
    // holding the org to community limits. A plain "enterprise" pill next to
    // free-tier numbers is what left admins with no idea why their ceilings
    // dropped, so the chip has to say it.
    render(<PlanChip edition="enterprise" licensed={false} />);
    expect(screen.getByText('enterprise (inactive)')).toBeInTheDocument();
  });

  it('does not mark the free tier inactive', () => {
    // Community is unlicensed by definition -- "community (inactive)" would be
    // telling a free org that something it never had has expired.
    render(<PlanChip edition="community" licensed={false} />);
    expect(screen.getByText('community')).toBeInTheDocument();
  });

  it('renders plainly when licence status is unknown', () => {
    // Default for callers that have no flag, and for a backend predating it.
    render(<PlanChip edition="enterprise" />);
    expect(screen.getByText('enterprise')).toBeInTheDocument();
  });
});

describe('UpgradeLink', () => {
  it('points at the published pricing page in a new tab', () => {
    render(<UpgradeLink />);
    const link = screen.getByRole('link', { name: /upgrade/i });
    expect(link).toHaveAttribute('href', UPGRADE_URL);
    expect(link).toHaveAttribute('href', 'https://rhesis.ai/pricing');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });
});
