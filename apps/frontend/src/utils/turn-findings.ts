import type {
  GoalEvaluation,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import { isGoalMetricName } from '@/utils/test-result-status';

/**
 * One thing a metric said about a conversation: a Goal Achievement criterion, or a whole
 * metric's verdict. `relevant_turns` are the turns it rests on.
 */
export interface TurnFinding {
  /** Unique across a conversation's findings, for React keys. */
  key: string;
  metric: string;
  /** The criterion text, or the metric name for a metric without criteria. */
  label: string;
  met: boolean;
  evidence: string;
  kind?: 'required' | 'prohibited';
  relevant_turns: number[];
  /** True when the finding cited every turn and was promoted to conversation-level. */
  conversationLevel?: boolean;
}

export type TurnStatus = 'Pass' | 'Fail';

const DEFAULT_GOAL_METRIC = 'Goal Achievement';

/**
 * Every finding on a conversation: one per Goal Achievement criterion, plus one per other
 * metric with a verdict. Inconclusive and errored metrics say nothing about any turn.
 */
export function buildTurnFindings(
  goalEvaluation?: GoalEvaluation,
  metrics: Record<string, MetricResult> = {},
  turnCount?: number
): TurnFinding[] {
  const entries = Object.entries(metrics);
  const [goalMetric, goalResult] = entries.find(([name]) =>
    isGoalMetricName(name)
  ) ?? [DEFAULT_GOAL_METRIC, undefined];

  // A re-score stores fresh criteria on the metric; goal_evaluation keeps the live run's.
  const criteria = (
    goalResult?.criteria_evaluations ??
    goalEvaluation?.criteria_evaluations ??
    []
  ).map((c, i) => ({
    // The index is part of the key because two criteria can carry identical text.
    key: `${goalMetric}-${i}`,
    metric: goalMetric,
    label: c.criterion,
    met: c.met,
    evidence: c.evidence,
    kind: c.kind,
    relevant_turns: c.relevant_turns ?? [],
  }));

  const others = entries
    .filter(
      ([name, m]) =>
        !isGoalMetricName(name) &&
        typeof m.is_successful === 'boolean' &&
        !m.error
    )
    .map(([name, m]) => ({
      key: name,
      metric: name,
      label: name,
      met: m.is_successful === true,
      evidence: m.reason,
      relevant_turns: m.relevant_turns ?? [],
    }));

  const all = [...criteria, ...others];

  // A finding that cites every turn is a conversation-level verdict, not a per-turn one.
  // Mark it so per-turn queries skip it, while keeping relevant_turns for the soft indicator.
  if (turnCount && turnCount > 1) {
    return all.map(f =>
      new Set(f.relevant_turns).size >= turnCount
        ? { ...f, conversationLevel: true }
        : f
    );
  }
  return all;
}

export function findingsForTurn(
  findings: TurnFinding[],
  turn: number
): TurnFinding[] {
  return findings.filter(
    f => !f.conversationLevel && f.relevant_turns.includes(turn)
  );
}

/** Failed if any finding citing the turn failed, passed if only passing ones cite it. */
export function turnStatus(
  findings: TurnFinding[],
  turn: number
): TurnStatus | undefined {
  const cited = findingsForTurn(findings, turn);
  if (cited.length === 0) return undefined;
  return cited.some(f => !f.met) ? 'Fail' : 'Pass';
}

/** Failures no turn carries, e.g. a judgment about the conversation as a whole. */
export function uncitedFailures(findings: TurnFinding[]): TurnFinding[] {
  return findings.filter(
    f => !f.met && (f.relevant_turns.length === 0 || f.conversationLevel)
  );
}

/** Whether any conversation-level finding cites this turn. */
export function turnHasConversationFindings(
  findings: TurnFinding[],
  turn: number
): boolean {
  return findings.some(
    f => f.conversationLevel && f.relevant_turns.includes(turn)
  );
}
