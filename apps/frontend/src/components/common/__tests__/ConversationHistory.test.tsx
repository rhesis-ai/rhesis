import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import ConversationHistory from '../ConversationHistory';

jest.mock('@/components/common/StatusChip', () => ({
  __esModule: true,
  default: ({ status }: { status: string }) => (
    <span data-testid="status-chip">{status}</span>
  ),
}));

jest.mock('@/components/common/ProjectIcons', () => ({
  getProjectIconComponent: jest.fn(() => () => (
    <span data-testid="project-icon" />
  )),
}));

function renderConversation(
  props: Partial<React.ComponentProps<typeof ConversationHistory>> = {}
) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <ConversationHistory conversationSummary={[]} {...props} />
    </ThemeProvider>
  );
}

// Component filters by penelope_message || target_response
function makeTurn(num: number) {
  return {
    turn: num,
    penelope_message: `Penelope message ${num}`,
    target_response: `Target response ${num}`,
    success: true,
    latency_ms: 100,
  };
}

describe('ConversationHistory', () => {
  it('shows "No conversation history available" for an empty conversation', () => {
    renderConversation();
    expect(
      screen.getByText(/no conversation history available/i)
    ).toBeInTheDocument();
  });

  it('renders turn content when conversationSummary has entries', () => {
    renderConversation({ conversationSummary: [makeTurn(1)] });
    expect(screen.getByText('Penelope message 1')).toBeInTheDocument();
    expect(screen.getByText('Target response 1')).toBeInTheDocument();
  });

  it('renders multiple turns', () => {
    renderConversation({
      conversationSummary: [makeTurn(1), makeTurn(2)],
    });
    expect(screen.getByText('Penelope message 1')).toBeInTheDocument();
    expect(screen.getByText('Penelope message 2')).toBeInTheDocument();
    expect(screen.getByText(/turn 1/i)).toBeInTheDocument();
    expect(screen.getByText(/turn 2/i)).toBeInTheDocument();
  });

  it('calls onResponseClick when target response is clicked', async () => {
    const user = userEvent.setup();
    const onResponseClick = jest.fn();

    renderConversation({
      conversationSummary: [makeTurn(1)],
      onResponseClick,
    });

    await user.click(screen.getByText('Target response 1'));
    expect(onResponseClick).toHaveBeenCalledWith(1);
  });

  it('shows "Conversation Concluded" chip at the end', () => {
    renderConversation({ conversationSummary: [makeTurn(1)] });
    expect(screen.getByText(/conversation concluded/i)).toBeInTheDocument();
  });

  it('shows "Confirmed" chip when hasExistingReview=true and reviewMatchesAutomated=true', () => {
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingReview: true,
      reviewMatchesAutomated: true,
    });
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
  });

  it('shows confirm button when hasExistingReview=false and onConfirmAutomatedReview is provided', () => {
    const onConfirmAutomatedReview = jest.fn();
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingReview: false,
      onConfirmAutomatedReview,
    });
    // The confirm button is an IconButton — look by role
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('calls onConfirmAutomatedReview when the confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirmAutomatedReview = jest.fn();

    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingReview: false,
      onConfirmAutomatedReview,
    });

    await user.click(screen.getByRole('button'));
    expect(onConfirmAutomatedReview).toHaveBeenCalled();
  });

  it('skips turns that have no penelope_message or target_response', () => {
    const silentTurn = {
      turn: 1,
      penelope_message: '',
      target_response: '',
      success: true,
    };
    renderConversation({ conversationSummary: [silentTurn] });
    expect(
      screen.getByText(/no conversation history available/i)
    ).toBeInTheDocument();
  });
});
