import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import TestDetailEvaluationTab from '../TestDetailEvaluationTab';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

const turn = (n: number) => ({
  turn: n,
  timestamp: '',
  session_id: '',
  penelope_reasoning: '',
  penelope_message: `user ${n}`,
  target_response: `bot ${n}`,
  success: true,
});

// The red-flag example: every goal criterion failed, plus the requirement's metric.
const multiTurnResult = {
  id: u(1),
  test_configuration_id: u(2),
  execution: 'ok',
  verdict: 'fail',
  test: {
    id: u(3),
    requirement: { id: u(4), name: 'Escalates Genuine Red Flags' },
  },
  test_output: {
    conversation_summary: [turn(1), turn(2), turn(3)],
    goal_evaluation: {
      all_criteria_met: false,
      reason: 'The system failed 2 of 2 criteria.',
      evidence: [],
      criteria_evaluations: [
        {
          criterion: 'Escalate breathing difficulty',
          kind: 'required',
          met: false,
          evidence: 'Kept asking history questions.',
          relevant_turns: [1, 2, 3],
        },
        {
          criterion: 'Reassure the user',
          kind: 'prohibited',
          met: false,
          evidence: 'Said it was glad they felt better.',
          relevant_turns: [3],
        },
      ],
    },
  },
  test_metrics: {
    execution_time: 1,
    metrics: {
      'Goal Achievement': {
        score: 0,
        reason: 'The system failed 2 of 2 criteria.',
        backend: 'rhesis',
        description: '',
        is_successful: false,
      },
      'Red Flag Escalation Check': {
        score: 'Fail',
        reason: 'Did not escalate.',
        backend: 'rhesis',
        description: '',
        is_successful: false,
        relevant_turns: [1, 2, 3],
      },
    },
  },
} as unknown as TestResultDetail;

function renderTab(
  props: Partial<React.ComponentProps<typeof TestDetailEvaluationTab>> = {}
) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <TestDetailEvaluationTab
        test={multiTurnResult}
        metricsSource="requirement"
        {...props}
      />
    </ThemeProvider>
  );
}

describe('TestDetailEvaluationTab', () => {
  it('counts goal criteria and other metrics as checks', () => {
    renderTab();
    expect(screen.getByText('0 of 3 checks passed')).toBeInTheDocument();
  });

  it('groups checks by the test and by its requirement', () => {
    renderTab();
    expect(
      screen.getByRole('heading', { name: 'This test' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: 'Requirement: Escalates Genuine Red Flags',
      })
    ).toBeInTheDocument();
    expect(screen.queryByText('Goal Achievement')).not.toBeInTheDocument();
  });

  it('splits the test checks into must do and must not do', () => {
    renderTab();
    expect(screen.getByText('Must do')).toBeInTheDocument();
    expect(screen.getByText('Must not do')).toBeInTheDocument();
  });

  it('tags only checks that cite some turns, not all of them', () => {
    renderTab();
    expect(screen.getByText('Turn 3')).toBeInTheDocument();
    expect(screen.queryByText('All turns')).not.toBeInTheDocument();
  });

  it('annotates Goal Achievement from the test group, and a metric from its row', async () => {
    const user = userEvent.setup();
    const onAnnotateMetric = jest.fn();
    renderTab({ onAnnotateMetric });

    const buttons = screen.getAllByRole('button', { name: 'Annotate' });
    expect(buttons).toHaveLength(2);
    await user.click(buttons[0]);
    await user.click(buttons[1]);
    expect(onAnnotateMetric).toHaveBeenNthCalledWith(1, 'Goal Achievement');
    expect(onAnnotateMetric).toHaveBeenNthCalledWith(
      2,
      'Red Flag Escalation Check'
    );
  });

  it('keeps the reasoning closed until asked', async () => {
    const user = userEvent.setup();
    renderTab();
    const toggle = screen.getByRole('button', { name: /reasoning/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(
      within(toggle.parentElement as HTMLElement).getByText(
        'The system failed 2 of 2 criteria.'
      )
    ).toBeInTheDocument();
  });
});
