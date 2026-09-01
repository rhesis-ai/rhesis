import { render, screen } from '@testing-library/react';
import { UpgradeLink } from '@/components/common/QuotaChips';
import { UPGRADE_URL } from '@/constants/quota';

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
