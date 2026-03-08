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
      <ArchitectMessageBubble
        message={createMessage({ role: 'user' })}
      />
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
        <ArchitectMessageBubble
          message={createMessage()}
          showActions={false}
        />
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

      expect(
        screen.getByTestId('CheckCircleOutlineIcon')
      ).toBeInTheDocument();
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
              { tool: 'list_endpoints', description: 'Listing endpoints' },
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
            activeTools: [{ tool: 'list_metrics' }],
            completedTools: [],
          }}
        />
      );

      expect(screen.getByText('list_metrics')).toBeInTheDocument();
    });
  });

  describe('copy functionality', () => {
    it('copies message content to clipboard', async () => {
      const writeText = jest.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText },
      });

      render(<ArchitectMessageBubble message={createMessage()} />);

      const copyButton = screen.getByTestId('ContentCopyIcon').closest(
        'button'
      ) as HTMLButtonElement;
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(writeText).toHaveBeenCalledWith('Hello from the architect');
      });
    });
  });
});
