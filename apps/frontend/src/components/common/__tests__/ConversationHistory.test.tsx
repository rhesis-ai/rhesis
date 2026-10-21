import React from 'react';
import { render, screen, within } from '@testing-library/react';
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

  it('ends with a divider saying how many turns there were', () => {
    renderConversation({ conversationSummary: [makeTurn(1), makeTurn(2)] });
    expect(
      screen.getByText('Conversation ended after 2 turns')
    ).toBeInTheDocument();
  });

  it('says who confirmed the verdict once it was reviewed', () => {
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: true,
      annotationMatchesAutomated: true,
      reviewerName: 'Ada',
      onConfirmAutomatedAnnotation: jest.fn(),
    });
    expect(screen.getByText('Verdict confirmed by Ada')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Confirm verdict' })
    ).not.toBeInTheDocument();
  });

  it('lets a reviewer undo their review when allowed', async () => {
    const user = userEvent.setup();
    const onUndoReview = jest.fn();
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: true,
      annotationMatchesAutomated: true,
      onUndoReview,
    });
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    expect(onUndoReview).toHaveBeenCalledTimes(1);
  });

  it('shows no Undo without the handler', () => {
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: true,
      annotationMatchesAutomated: true,
    });
    expect(
      screen.queryByRole('button', { name: 'Undo' })
    ).not.toBeInTheDocument();
  });

  it('says the verdict was changed when the review disagreed', () => {
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: true,
      annotationMatchesAutomated: false,
      reviewerName: 'Ada',
    });
    expect(screen.getByText('Verdict changed by Ada')).toBeInTheDocument();
  });

  it('offers to override an unreviewed verdict', async () => {
    const user = userEvent.setup();
    const onOverrideVerdict = jest.fn();
    renderConversation({
      conversationSummary: [makeTurn(1)],
      onOverrideVerdict,
    });
    expect(
      screen.getByText('Automated verdict · not reviewed yet')
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Override' }));
    expect(onOverrideVerdict).toHaveBeenCalledTimes(1);
  });

  it('shows confirm button when hasExistingAnnotation=false and onConfirmAutomatedAnnotation is provided', () => {
    const onConfirmAutomatedAnnotation = jest.fn();
    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: false,
      onConfirmAutomatedAnnotation,
    });
    expect(
      screen.getByRole('button', { name: 'Confirm verdict' })
    ).toBeInTheDocument();
  });

  it('calls onConfirmAutomatedAnnotation when the confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirmAutomatedAnnotation = jest.fn();

    renderConversation({
      conversationSummary: [makeTurn(1)],
      hasExistingAnnotation: false,
      onConfirmAutomatedAnnotation,
    });

    await user.click(screen.getByRole('button', { name: 'Confirm verdict' }));
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
      screen
        .queryAllByTestId('status-chip')
        .filter(chip => !chip.closest('[data-testid="result-summary"]'))
        .map(chip => chip.textContent);

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

    it('shows a failure that cites every turn on every turn', () => {
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        goalEvaluation: goalEvaluation(true, [1]),
        metrics: redFlag(false, [1, 2]),
      });
      // The passing criterion only cites turn 1, but the failed metric cites both.
      expect(turnStatuses()).toEqual(['Fail', 'Fail']);
      expect(screen.queryByText('Evaluated')).not.toBeInTheDocument();
    });

    it("lists a turn's checks in the same cards as the Evaluation tab", async () => {
      const user = userEvent.setup();
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        goalEvaluation: goalEvaluation(false, [1]),
        metrics: redFlag(true, [1, 2]),
        requirementName: 'Escalates Red Flags',
        metricsSource: 'requirement',
      });
      const [toggle] = screen.getAllByRole('button', { name: /^findings/i });
      // Turn 1: the criterion failed, the metric passed.
      expect(toggle).toHaveTextContent('Findings · 1 failed');
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      await user.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
      expect(
        screen.getByRole('heading', { name: 'This test' })
      ).toBeInTheDocument();
      expect(screen.getByText('Must do')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', {
          name: 'Requirement: Escalates Red Flags',
        })
      ).toBeInTheDocument();
      // The turn is already chosen, so checks carry no turn tags here.
      const card = screen
        .getByRole('heading', { name: 'This test' })
        .closest('.MuiPaper-root') as HTMLElement;
      expect(within(card).queryByText(/^Turns? \d/)).not.toBeInTheDocument();
      expect(screen.queryByText('Met')).not.toBeInTheDocument();
    });

    it('sums up the checks after the conversation, not above it', () => {
      renderConversation({
        conversationSummary: [makeTurn(1), makeTurn(2)],
        metrics: redFlag(false),
      });
      const summary = screen.getByTestId('result-summary');
      expect(summary).toHaveTextContent('Fail');
      expect(summary).toHaveTextContent('0 of 1 check passed');
      expect(turnStatuses()).toEqual([]);
      expect(
        screen.queryByRole('button', { name: /see full evaluation/i })
      ).not.toBeInTheDocument();
    });

    it('collapses a confirmed pass to one line until asked', async () => {
      const user = userEvent.setup();
      renderConversation({
        conversationSummary: [makeTurn(1)],
        metrics: redFlag(true, [1]),
        hasExistingAnnotation: true,
        annotationMatchesAutomated: true,
        reviewerName: 'Ada',
      });
      const summary = screen.getByTestId('result-summary');
      expect(summary).toHaveTextContent('Confirmed by Ada');
      expect(within(summary).queryByText('Red Flag Escalation')).toBeNull();
      await user.click(screen.getByRole('button', { name: 'Show checks' }));
      expect(
        within(summary).getByText('Red Flag Escalation')
      ).toBeInTheDocument();
    });

    it('collapses right after a pass is confirmed, like a reload would', () => {
      const props = {
        conversationSummary: [makeTurn(1)],
        metrics: redFlag(true, [1]),
        onConfirmAutomatedAnnotation: jest.fn(),
      };
      const { rerender } = renderConversation(props);
      expect(
        screen.getByRole('button', { name: 'Confirm verdict' })
      ).toBeInTheDocument();
      rerender(
        <ThemeProvider theme={lightTheme}>
          <ConversationHistory
            {...props}
            hasExistingAnnotation
            annotationMatchesAutomated
          />
        </ThemeProvider>
      );
      expect(
        screen.getByRole('button', { name: 'Show checks' })
      ).toBeInTheDocument();
    });

    it('prefers the given result status, e.g. after a human override', () => {
      renderConversation({
        conversationSummary: [makeTurn(1)],
        metrics: redFlag(false),
        resultStatus: 'Pass',
      });
      expect(screen.getByTestId('result-summary')).toHaveTextContent('Pass');
    });

    it('links to the evaluation when a handler is given', async () => {
      const user = userEvent.setup();
      const onShowEvaluation = jest.fn();
      renderConversation({
        conversationSummary: [makeTurn(1)],
        metrics: redFlag(false),
        onShowEvaluation,
      });
      await user.click(
        screen.getByRole('button', { name: /see full evaluation/i })
      );
      expect(onShowEvaluation).toHaveBeenCalledTimes(1);
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
