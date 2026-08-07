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
  it('defaults to the Resources tab when no ?tab= param is present', () => {
    render(<UsageDetailTabs />);

    expect(screen.getByTestId('overview-tab')).toBeVisible();
  });

  it('shows the Timeline tab when ?tab=timeline', () => {
    mockSearchParams = new URLSearchParams('tab=timeline');

    render(<UsageDetailTabs />);

    expect(screen.getByTestId('history-tab')).toBeVisible();
  });

  it('falls back to Resources for an unrecognized ?tab= value', () => {
    mockSearchParams = new URLSearchParams('tab=nonsense');

    render(<UsageDetailTabs />);

    expect(screen.getByTestId('overview-tab')).toBeVisible();
  });

  it('pushes the timeline tab key when clicking "Timeline"', () => {
    render(<UsageDetailTabs />);

    fireEvent.click(screen.getByText('Timeline'));

    expect(mockPush).toHaveBeenCalledWith('?tab=timeline', { scroll: false });
  });

  it('renders both tab labels', () => {
    render(<UsageDetailTabs />);

    expect(screen.getByText('Resources')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
  });
});
