import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import InsightsEmptyState from '../InsightsEmptyState';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
}));

afterEach(() => {
  jest.clearAllMocks();
});

describe('InsightsEmptyState', () => {
  it('renders card empty state for no endpoints', async () => {
    const user = userEvent.setup();
    render(<InsightsEmptyState variant="no-endpoints" />);

    expect(
      screen.getByRole('heading', { name: 'No endpoints in this project' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go to Endpoints' })).toHaveClass(
      'MuiButton-outlined'
    );

    await user.click(screen.getByRole('button', { name: 'Go to Endpoints' }));
    expect(mockPush).toHaveBeenCalledWith('/endpoints');
  });

  it('renders card empty state for no test results', async () => {
    const user = userEvent.setup();
    render(<InsightsEmptyState variant="no-test-results" />);

    expect(
      screen.getByRole('heading', { name: 'No test results yet' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go to Test Sets' })).toHaveClass(
      'MuiButton-outlined'
    );

    await user.click(screen.getByRole('button', { name: 'Go to Test Sets' }));
    expect(mockPush).toHaveBeenCalledWith('/test-sets');
  });
});
