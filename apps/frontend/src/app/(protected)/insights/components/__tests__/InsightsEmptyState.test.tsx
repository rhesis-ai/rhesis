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

  it('names the endpoint and offers to switch to one with results', async () => {
    const user = userEvent.setup();
    const onSelectEndpoint = jest.fn();
    render(
      <InsightsEmptyState
        variant="no-test-results"
        endpointName="Internal Policy Agent"
        endpointsWithResults={[{ id: 'ep-2', name: 'Standards Agent' }]}
        hasOtherEndpoints
        onSelectEndpoint={onSelectEndpoint}
      />
    );

    expect(
      screen.getByRole('heading', {
        name: 'No test results for Internal Policy Agent yet',
      })
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: 'Show Standards Agent' })
    );
    expect(onSelectEndpoint).toHaveBeenCalledWith('ep-2');
  });

  it('offers to switch endpoint when other endpoints have no results either', async () => {
    const user = userEvent.setup();
    const onSwitchEndpoint = jest.fn();
    render(
      <InsightsEmptyState
        variant="no-test-results"
        endpointName="Internal Policy Agent"
        hasOtherEndpoints
        onSelectEndpoint={jest.fn()}
        onSwitchEndpoint={onSwitchEndpoint}
      />
    );

    expect(
      screen.getByText(/or switch to another endpoint/)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /^Show / })
    ).not.toBeInTheDocument();

    expect(screen.getByRole('button', { name: 'Go to Test Sets' })).toHaveClass(
      'MuiButton-contained'
    );
    expect(screen.getByRole('button', { name: 'Switch endpoint' })).toHaveClass(
      'MuiButton-outlined'
    );

    await user.click(screen.getByRole('button', { name: 'Switch endpoint' }));
    expect(onSwitchEndpoint).toHaveBeenCalled();
  });

  it('hides switch endpoint when the project has only one endpoint', () => {
    render(
      <InsightsEmptyState
        variant="no-test-results"
        endpointName="Standards Agent"
        onSwitchEndpoint={jest.fn()}
      />
    );

    expect(
      screen.queryByRole('button', { name: 'Switch endpoint' })
    ).not.toBeInTheDocument();
  });
});
