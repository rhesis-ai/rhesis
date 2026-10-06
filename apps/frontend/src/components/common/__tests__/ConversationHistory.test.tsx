import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import ConversationHistory from '../ConversationHistory';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok' },
    status: 'authenticated',
  }),
}));

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
    penelope_reasoning: '',
    timestamp: new Date().toISOString(),
    session_id: 'sess-1',
    success: true,
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

  it('shows "Confirmed" chip when hasExistingAnnotation=true and annotationMatchesAutomated=true', () => {
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: true,
      annotationMatchesAutomated: true,
    });
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
  });

  it('shows confirm button when hasExistingAnnotation=false and onConfirmAutomatedAnnotation is provided', () => {
    const onConfirmAutomatedAnnotation = jest.fn();
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: false,
      onConfirmAutomatedAnnotation,
    });
    // The confirm button is an IconButton — look by role
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('calls onConfirmAutomatedAnnotation when the confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirmAutomatedAnnotation = jest.fn();

    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: false,
      onConfirmAutomatedAnnotation,
    });

    await user.click(screen.getByRole('button'));
    expect(onConfirmAutomatedAnnotation).toHaveBeenCalled();
  });

  it('skips turns that have no penelope_message or target_response', () => {
    const silentTurn = {
      turn: 1,
      penelope_message: '',
      target_response: '',
      penelope_reasoning: '',
      timestamp: new Date().toISOString(),
      session_id: 'sess-1',
      success: true,
    };
    renderConversation({ conversationSummary: [silentTurn] });
    expect(
      screen.getByText(/no conversation history available/i)
    ).toBeInTheDocument();
  });

  describe('turn status from metric findings', () => {
    const turnStatuses = () =>
      screen.getAllByTestId('status-chip').map(chip => chip.textContent);

    const goalEvaluation = (met: boolean, relevant_turns: number[]) => ({
      all_criteria_met: met,
      reason: '',
      evidence: [],
      criteria_evaluations: [
        {
          criterion: 'Recommend immediate medical consultation',
          kind: 'required' as const,
          met,
          evidence: 'Repeated a canned response.',
          relevant_turns,
        },
      ],
    });

    const redFlag = (is_successful: boolean, relevant_turns?: number[]) => ({
      'Red Flag Escalation': {
        score: is_successful ? 'Escalated' : 'Ignored',
        reason: 'Did not escalate chest pain.',
        backend: 'rhesis',
        description: '',
        is_successful,
        relevant_turns,
      },
    });

    it('fails cited turns and shows no status on uncited ones', () => {
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2), makeTurn(3)],
        goalEvaluation: goalEvaluation(false, [1, 2]),
      });
      expect(turnStatuses()).toEqual(['Fail', 'Fail']);
    });

    it('shows Error on an uncited turn whose endpoint call failed', () => {
      renderConversation({
        conversationSummary: [{ ...makeTurn(1), success: false }],
      });
      expect(turnStatuses()).toEqual(['Error']);
    });

    it('a failed metric fails a turn a passed criterion also cites', () => {
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2), makeTurn(3)],
        goalEvaluation: goalEvaluation(true, [1, 2]),
        metrics: redFlag(false, [2]),
      });
      // Goal criterion cites [1,2] out of 3 turns → stays per-turn.
      // Turn 1: Pass (only the passing goal criterion), Turn 2: Fail (criterion + failed metric).
      expect(turnStatuses()).toEqual(['Pass', 'Fail']);
    });

    it('promotes a finding citing all turns to conversation-level', () => {
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        goalEvaluation: goalEvaluation(true, [1, 2]),
        metrics: redFlag(false, [2]),
      });
      // Goal criterion cites all 2 turns → promoted to conversation-level.
      // Turn 1: no per-turn verdict → soft "Evaluated" chip. Turn 2: failed metric → Fail.
      expect(turnStatuses()).toEqual(['Fail']);
      expect(screen.getByText('Evaluated')).toBeInTheDocument();
    });

    it('shows a failure that cites no turn above the conversation', () => {
      renderConversation({
        conversationSummary: [makeTurn(1)],
        metrics: redFlag(false),
      });
      expect(
        screen.getByText(/failed on the conversation as a whole/i)
      ).toBeInTheDocument();
      expect(screen.getByText('Red Flag Escalation')).toBeInTheDocument();
      expect(screen.queryByTestId('status-chip')).not.toBeInTheDocument();
    });

    it('passes the shown turn status to the annotate handler', async () => {
      const user = userEvent.setup();
      const onAnnotateTurn = jest.fn();
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        onAnnotateTurn,
        goalEvaluation: goalEvaluation(false, [1]),
      });

      const [cited, uncited] = screen.getAllByRole('button', {
        name: /annotate this turn/i,
      });
      await user.click(cited);
      await user.click(uncited);
      expect(onAnnotateTurn).toHaveBeenNthCalledWith(1, 1, false);
      expect(onAnnotateTurn).toHaveBeenNthCalledWith(2, 2, undefined);
    });
  });

  describe('create test from turn', () => {
    it('shows no create-test button unless a handler is given', () => {
      renderConversation({ conversationSummary: [makeTurn(1)] });
      expect(
        screen.queryByRole('button', { name: /create single-turn test/i })
      ).not.toBeInTheDocument();
    });

    it('calls the handler with the turn number of the clicked turn', async () => {
      const user = userEvent.setup();
      const onCreateTestFromTurn = jest.fn();
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        onCreateTestFromTurn,
      });

      await user.click(
        screen.getByRole('button', {
          name: 'Create single-turn test from turn 2',
        })
      );
      expect(onCreateTestFromTurn).toHaveBeenCalledWith(2);
    });
  });
});
