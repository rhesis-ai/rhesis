import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import StreamingIndicator from '../StreamingIndicator';
import { StreamingState } from '@/hooks/useArchitectChat';

function createState(overrides: Partial<StreamingState> = {}): StreamingState {
  return {
    isThinking: false,
    activeTools: [],
    completedTools: [],
    ...overrides,
  };
}

describe('StreamingIndicator', () => {
  it('shows thinking indicator when isThinking is true', () => {
    render(<StreamingIndicator state={createState({ isThinking: true })} />);

    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
  });

  it('shows thinking text when no iteration', () => {
    render(<StreamingIndicator state={createState({ isThinking: true })} />);

    expect(screen.getByText('Thinking')).toBeInTheDocument();
  });

  it('shows step number when iteration is provided', () => {
    render(
      <StreamingIndicator
        state={createState({ isThinking: true, currentIteration: 5 })}
      />
    );

    expect(screen.getByText('Thinking (step 5)')).toBeInTheDocument();
  });

  it('does not show thinking indicator when isThinking is false', () => {
    render(<StreamingIndicator state={createState({ isThinking: false })} />);

    expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();
  });

  it('renders active tool calls with build icon', () => {
    render(
      <StreamingIndicator
        state={createState({
          activeTools: [
            { tool: 'list_endpoints', description: 'Listing endpoints' },
            { tool: 'list_metrics', description: 'Listing metrics' },
          ],
        })}
      />
    );

    expect(screen.getByText('Listing endpoints')).toBeInTheDocument();
    expect(screen.getByText('Listing metrics')).toBeInTheDocument();
  });

  it('falls back to tool name when description is missing', () => {
    render(
      <StreamingIndicator
        state={createState({
          activeTools: [{ tool: 'list_behaviors' }],
        })}
      />
    );

    expect(screen.getByText('list_behaviors')).toBeInTheDocument();
  });

  it('renders completed successful tools with check icon', () => {
    render(
      <StreamingIndicator
        state={createState({
          completedTools: [
            {
              tool: 'list_endpoints',
              description: 'Listed endpoints',
              success: true,
            },
          ],
        })}
      />
    );

    expect(screen.getByText('Listed endpoints')).toBeInTheDocument();
    expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
  });

  it('renders completed failed tools with error icon', () => {
    render(
      <StreamingIndicator
        state={createState({
          completedTools: [
            {
              tool: 'check_endpoint',
              description: 'Checking endpoint',
              success: false,
            },
          ],
        })}
      />
    );

    expect(screen.getByText('Checking endpoint')).toBeInTheDocument();
    expect(screen.getByTestId('ErrorIcon')).toBeInTheDocument();
  });

  it('renders a mix of active and completed tools', () => {
    render(
      <StreamingIndicator
        state={createState({
          isThinking: true,
          activeTools: [
            { tool: 'create_metric', description: 'Creating metric' },
          ],
          completedTools: [
            {
              tool: 'list_metrics',
              description: 'Listed metrics',
              success: true,
            },
          ],
        })}
      />
    );

    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    expect(screen.getByText('Creating metric')).toBeInTheDocument();
    expect(screen.getByText('Listed metrics')).toBeInTheDocument();
  });

  it('renders nothing meaningful when state is empty', () => {
    const { container } = render(<StreamingIndicator state={createState()} />);

    // Should still render the container but no tool or thinking text
    expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();
    expect(
      container.querySelector('[role="progressbar"]')
    ).not.toBeInTheDocument();
  });
});
