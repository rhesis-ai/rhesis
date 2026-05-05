import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ArchitectMessageBubble from '../ArchitectMessageBubble';
import { ArchitectChatMessage } from '@/hooks/useArchitectChat';

// Mock MarkdownContent to avoid markdown rendering complexity
jest.mock('@/components/common/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => (
    <div data-testid="markdown-content">{content}</div>
  ),
}));

// Mock UserAvatar
jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: ({ userName }: { userName?: string }) => (
    <div data-testid="user-avatar">{userName}</div>
  ),
}));

function createMessage(
  overrides: Partial<ArchitectChatMessage> = {}
): ArchitectChatMessage {
  return {
    id: 'msg-1',
    role: 'assistant',
    content: 'Hello from the architect',
    timestamp: new Date('2026-03-08T10:30:00'),
    ...overrides,
  };
}

describe('ArchitectMessageBubble', () => {
  it('renders assistant message content', () => {
    render(<ArchitectMessageBubble message={createMessage()} />);

    expect(screen.getByTestId('markdown-content')).toHaveTextContent(
      'Hello from the architect'
    );
  });

  it('renders user message with user avatar', () => {
    render(
      <ArchitectMessageBubble
        message={createMessage({ role: 'user', content: 'My question' })}
        userName="Alice"
      />
    );

    expect(screen.getByTestId('user-avatar')).toHaveTextContent('Alice');
    expect(screen.getByTestId('markdown-content')).toHaveTextContent(
      'My question'
    );
  });

  it('renders engineering icon for assistant messages', () => {
    render(<ArchitectMessageBubble message={createMessage()} />);

    expect(screen.getByTestId('EngineeringIcon')).toBeInTheDocument();
  });

  it('renders error icon for error messages', () => {
    render(
      <ArchitectMessageBubble
        message={createMessage({ isError: true, content: 'Error occurred' })}
      />
    );

    expect(screen.getByTestId('ErrorOutlineIcon')).toBeInTheDocument();
  });

  it('displays formatted timestamp', () => {
    render(<ArchitectMessageBubble message={createMessage()} />);

    // The exact format depends on locale, but the time should be present
    const timeText = screen.getByText(/\d{1,2}:\d{2}/);
    expect(timeText).toBeInTheDocument();
  });

  it('shows copy button for assistant messages', () => {
    render(<ArchitectMessageBubble message={createMessage()} />);

    expect(screen.getByTestId('ContentCopyIcon')).toBeInTheDocument();
  });

  it('does not show copy button for user messages', () => {
    render(
      <ArchitectMessageBubble message={createMessage({ role: 'user' })} />
    );

    expect(screen.queryByTestId('ContentCopyIcon')).not.toBeInTheDocument();
  });

  describe('action buttons', () => {
    it('shows Accept and Change buttons when showActions is true', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage()}
          showActions={true}
          onAccept={jest.fn()}
          onReject={jest.fn()}
        />
      );

      expect(
        screen.getByRole('button', { name: /accept/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /change/i })
      ).toBeInTheDocument();
    });

    it('does not show action buttons when showActions is false', () => {
      render(
        <ArchitectMessageBubble message={createMessage()} showActions={false} />
      );

      expect(
        screen.queryByRole('button', { name: /accept/i })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: /change/i })
      ).not.toBeInTheDocument();
    });

    it('does not show action buttons for user messages even if showActions is true', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ role: 'user' })}
          showActions={true}
        />
      );

      expect(
        screen.queryByRole('button', { name: /accept/i })
      ).not.toBeInTheDocument();
    });

    it('calls onAccept when Accept is clicked', () => {
      const onAccept = jest.fn();
      render(
        <ArchitectMessageBubble
          message={createMessage()}
          showActions={true}
          onAccept={onAccept}
          onReject={jest.fn()}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /accept/i }));
      expect(onAccept).toHaveBeenCalledTimes(1);
    });

    it('calls onReject when Change is clicked', () => {
      const onReject = jest.fn();
      render(
        <ArchitectMessageBubble
          message={createMessage()}
          showActions={true}
          onAccept={jest.fn()}
          onReject={onReject}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /change/i }));
      expect(onReject).toHaveBeenCalledTimes(1);
    });

    it('renders correct icons on action buttons', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage()}
          showActions={true}
          onAccept={jest.fn()}
          onReject={jest.fn()}
        />
      );

      expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
      expect(screen.getByTestId('EditIcon')).toBeInTheDocument();
    });
  });

  describe('streaming state', () => {
    it('shows thinking indicator', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: true,
            activeTools: [],
            completedTools: [],
          }}
        />
      );

      expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    });

    it('shows thinking with iteration step', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: true,
            currentIteration: 3,
            activeTools: [],
            completedTools: [],
          }}
        />
      );

      expect(screen.getByText(/step 3/i)).toBeInTheDocument();
    });

    it('shows active tool calls', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: false,
            activeTools: [
              {
                tool: 'list_endpoints',
                description: 'Listing endpoints',
                startedAt: 1000,
              },
            ],
            completedTools: [],
          }}
        />
      );

      expect(screen.getByText('Listing endpoints')).toBeInTheDocument();
    });

    it('shows completed tool calls with success icon', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: false,
            activeTools: [],
            completedTools: [
              {
                tool: 'list_endpoints',
                description: 'Listed endpoints',
                success: true,
                startedAt: 1000,
              },
            ],
          }}
        />
      );

      expect(screen.getByText('Listed endpoints')).toBeInTheDocument();
      expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
    });

    it('shows completed tool calls with error icon on failure', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: false,
            activeTools: [],
            completedTools: [
              {
                tool: 'check_endpoint',
                description: 'Checking endpoint',
                success: false,
                startedAt: 1000,
              },
            ],
          }}
        />
      );

      expect(screen.getByText('Checking endpoint')).toBeInTheDocument();
      expect(screen.getByTestId('ErrorIcon')).toBeInTheDocument();
    });

    it('falls back to tool name when no description is provided', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ content: '' })}
          streamingState={{
            isThinking: false,
            activeTools: [{ tool: 'list_metrics', startedAt: 1000 }],
            completedTools: [],
          }}
        />
      );

      expect(screen.getByText('list_metrics')).toBeInTheDocument();
    });
  });

  describe('waiting / done indicators', () => {
    it('shows the "Working…" spinner while a long task is running', () => {
      render(
        <ArchitectMessageBubble message={createMessage()} showWaitingSpinner />
      );

      expect(screen.getByText('Working…')).toBeInTheDocument();
      expect(screen.queryByText('Done.')).not.toBeInTheDocument();
    });

    it('shows the "Done." indicator when the long task has completed', () => {
      render(
        <ArchitectMessageBubble message={createMessage()} showTaskComplete />
      );

      expect(screen.getByText('Done.')).toBeInTheDocument();
      expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
      expect(screen.queryByText('Working…')).not.toBeInTheDocument();
    });

    it('prefers "Working…" over "Done." if both are accidentally true', () => {
      // The hook should never set both at once, but the bubble should
      // still degrade gracefully in case it does.
      render(
        <ArchitectMessageBubble
          message={createMessage()}
          showWaitingSpinner
          showTaskComplete
        />
      );

      expect(screen.getByText('Working…')).toBeInTheDocument();
      expect(screen.queryByText('Done.')).not.toBeInTheDocument();
    });

    it('shows neither indicator when both flags are off', () => {
      render(<ArchitectMessageBubble message={createMessage()} />);
      expect(screen.queryByText('Working…')).not.toBeInTheDocument();
      expect(screen.queryByText('Done.')).not.toBeInTheDocument();
    });
  });

  describe('task progress trail', () => {
    // Task-progress events are now routed into streamingState by the hook
    // and rendered through the same ToolCallList used for regular tool calls.
    // The bubble receives them via the streamingState prop (same as any
    // active assistant turn), so these tests verify that pathway.

    it('renders progress rows passed via streamingState while bubble is streaming', () => {
      render(
        <ArchitectMessageBubble
          message={createMessage({ isStreaming: true })}
          streamingState={{
            isThinking: false,
            currentIteration: 1,
            activeTools: [
              {
                tool: 't1',
                description: 'Running domain probing',
                startedAt: 1,
              },
            ],
            completedTools: [
              {
                tool: 't1',
                description: 'Starting exploration',
                success: true,
                startedAt: 0,
              },
            ],
          }}
          showWaitingSpinner
        />
      );

      expect(screen.getByText('Starting exploration')).toBeInTheDocument();
      expect(screen.getByText('Running domain probing')).toBeInTheDocument();
    });

    it('hides the footer "Working…" while streamingState has an active tool row', () => {
      // The inline spinner in the active ToolCallList row already signals
      // liveness — the footer spinner must not duplicate it.
      render(
        <ArchitectMessageBubble
          message={createMessage({ isStreaming: true })}
          streamingState={{
            isThinking: false,
            currentIteration: 1,
            activeTools: [
              {
                tool: 't1',
                description: 'Turn 1: probing endpoint',
                startedAt: 1,
              },
            ],
            completedTools: [],
          }}
          showWaitingSpinner
        />
      );

      expect(screen.queryByText('Working…')).toBeNull();
      expect(screen.getByText('Turn 1: probing endpoint')).toBeInTheDocument();
    });

    it('shows the footer "Working…" when no progress has arrived yet (empty streamingState)', () => {
      // Before the first task-progress event the streamingState trail is
      // empty; only the footer spinner should animate.
      render(
        <ArchitectMessageBubble
          message={createMessage({ isStreaming: true })}
          streamingState={{
            isThinking: false,
            currentIteration: 1,
            activeTools: [],
            completedTools: [],
          }}
          showWaitingSpinner
        />
      );

      expect(screen.getByText('Working…')).toBeInTheDocument();
    });

    it('shows the footer "Working…" when all trail entries are terminal (gap before agent resumes)', () => {
      // Between the final "completed" progress event and the agent's
      // THINKING / resumed turn, the streamingState still exists but
      // activeTools is empty. The footer fills that brief gap.
      render(
        <ArchitectMessageBubble
          message={createMessage({ isStreaming: true })}
          streamingState={{
            isThinking: false,
            currentIteration: 1,
            activeTools: [],
            completedTools: [
              {
                tool: 't1',
                description: 'Exploration completed',
                success: true,
                durationMs: 2000,
                startedAt: 0,
              },
            ],
          }}
          showWaitingSpinner
        />
      );

      expect(screen.getByText('Working…')).toBeInTheDocument();
    });

    it('shows "Done." and no trail rows once bubble is marked taskCompleted', () => {
      // After the task ends the bubble gets taskCompleted=true and
      // streamingState is cleared (undefined), so no rows are rendered.
      render(
        <ArchitectMessageBubble
          message={createMessage({ taskCompleted: true })}
          showWaitingSpinner={false}
          showTaskComplete
        />
      );

      expect(screen.getByText('Done.')).toBeInTheDocument();
    });
  });

  describe('copy functionality', () => {
    it('copies message content to clipboard', async () => {
      const writeText = jest.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(<ArchitectMessageBubble message={createMessage()} />);

      const copyButton = screen
        .getByTestId('ContentCopyIcon')
        .closest('button') as HTMLButtonElement;
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(writeText).toHaveBeenCalledWith('Hello from the architect');
      });
    });
  });
});
