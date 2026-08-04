import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import UsageDetailTabs from '../UsageDetailTabs';

const mockPush = jest.fn();
let mockSearchParams = new URLSearchParams();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockSearchParams,
}));

jest.mock('../UsageOverviewTab', () => ({
  __esModule: true,
  default: () => <div data-testid="overview-tab">overview content</div>,
}));

jest.mock('../UsageOverTimeTab', () => ({
  __esModule: true,
  default: () => <div data-testid="history-tab">history content</div>,
}));

beforeEach(() => {
  mockPush.mockReset();
  mockSearchParams = new URLSearchParams();
});

describe('UsageDetailTabs', () => {
  it('defaults to the Overview tab when no ?tab= param is present', () => {
    render(<UsageDetailTabs />);

    expect(screen.getByTestId('overview-tab')).toBeVisible();
  });

  it('shows the Usage over Time tab when ?tab=history', () => {
    mockSearchParams = new URLSearchParams('tab=history');

    render(<UsageDetailTabs />);

    expect(screen.getByTestId('history-tab')).toBeVisible();
  });

  it('falls back to Overview for an unrecognized ?tab= value', () => {
    mockSearchParams = new URLSearchParams('tab=nonsense');

    render(<UsageDetailTabs />);

    expect(screen.getByTestId('overview-tab')).toBeVisible();
  });

  it('pushes the history tab key when clicking "Usage over Time"', () => {
    render(<UsageDetailTabs />);

    fireEvent.click(screen.getByText('Usage over Time'));

    expect(mockPush).toHaveBeenCalledWith('?tab=history', { scroll: false });
  });

  it('renders both tab labels', () => {
    render(<UsageDetailTabs />);

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Usage over Time')).toBeInTheDocument();
  });
});
