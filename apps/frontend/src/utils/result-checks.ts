import type {
  CriterionEvaluation,
  GoalEvaluation,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import {
  MetricsSource,
  getMetricsSourceLabel,
} from '@/utils/api-client/interfaces/test-configuration';
import { isGoalMetricName } from '@/utils/test-result-status';
import type { TestResultStatus } from '@/constants/outcomes';

/**
 * One pass/fail statement about a test result: a Goal Achievement criterion, or a whole
 * metric. Goal Achievement passes only when every criterion does, so counting criteria in
 * place of that metric never contradicts the result's status.
 */
export interface ResultCheck {
  key: string;
  label: string;
  /** null when the check could not reach a verdict. */
  passed: boolean | null;
  reason: string;
  kind?: CriterionEvaluation['kind'];
  relevantTurns: number[];
  /** The metric that produced the check, which is what annotations target. */
  metric: string;
  result?: MetricResult;
}

export interface ResultCheckGroup {
  key: 'test' | 'metrics';
  title: string;
  checks: ResultCheck[];
  /** Set when the whole group is one metric, so it is annotated from the group header. */
  metric?: string;
}

interface ResultCheckInput {
  metrics?: Record<string, MetricResult>;
  goalEvaluation?: GoalEvaluation;
  requirementName?: string;
  metricsSource?: MetricsSource | string;
}

const DEFAULT_GOAL_METRIC = 'Goal Achievement';

const verdictOf = (m: MetricResult): boolean | null =>
  !m.error && typeof m.is_successful === 'boolean' ? m.is_successful : null;

function goalChecks(
  name: string,
  result: MetricResult | undefined,
  goalEvaluation?: GoalEvaluation
): ResultCheck[] {
  // A re-score stores fresh criteria on the metric; goal_evaluation keeps the live run's.
  const criteria =
    result?.criteria_evaluations ?? goalEvaluation?.criteria_evaluations ?? [];
  if (criteria.length === 0) {
    return result ? [metricCheck(name, result)] : [];
  }
  // Must-do first, then must-not-do; the index keeps criteria with identical text apart.
  return criteria
    .map((c, i) => ({
      key: `${name}-${i}`,
      label: c.criterion,
      passed: c.met,
      reason: c.evidence,
      kind: c.kind,
      relevantTurns: c.relevant_turns ?? [],
      metric: name,
    }))
    .sort(
      (a, b) =>
        Number(a.kind === 'prohibited') - Number(b.kind === 'prohibited')
    );
}

function metricCheck(name: string, result: MetricResult): ResultCheck {
  return {
    key: name,
    label: name,
    passed: verdictOf(result),
    reason: result.error || result.reason,
    relevantTurns: result.relevant_turns ?? [],
    metric: name,
    result,
  };
}

function metricsGroupTitle(
  requirementName?: string,
  metricsSource?: MetricsSource | string
): string {
  const fromRequirement =
    !metricsSource || metricsSource === MetricsSource.REQUIREMENT;
  if (fromRequirement && requirementName) {
    return `Requirement: ${requirementName}`;
  }
  if (metricsSource && !fromRequirement) {
    return getMetricsSourceLabel(metricsSource);
  }
  return 'Metrics';
}

/** A result's checks, grouped by where they come from: the test itself, or its metrics. */
export function buildResultChecks({
  metrics = {},
  goalEvaluation,
  requirementName,
  metricsSource,
}: ResultCheckInput): ResultCheckGroup[] {
  const entries = Object.entries(metrics);
  const goal = entries.find(([name]) => isGoalMetricName(name));
  const others = entries.filter(([name]) => !isGoalMetricName(name));
  // A live run can carry goal_evaluation criteria without the metric entry.
  const [goalName, goalResult] =
    goal ??
    (goalEvaluation?.criteria_evaluations?.length
      ? [DEFAULT_GOAL_METRIC, undefined]
      : []);

  const groups: ResultCheckGroup[] = [];
  if (goalName) {
    groups.push({
      key: 'test',
      title: 'This test',
      checks: goalChecks(goalName, goalResult, goalEvaluation),
      metric: goalName,
    });
  }
  if (others.length > 0) {
    groups.push({
      key: 'metrics',
      title: metricsGroupTitle(requirementName, metricsSource),
      checks: others.map(([name, result]) => metricCheck(name, result)),
    });
  }
  return groups;
}

/** Checks with a verdict, and how many of them passed. */
export function countChecks(checks: ResultCheck[]): {
  passed: number;
  total: number;
} {
  const scored = checks.filter(c => c.passed !== null);
  return {
    passed: scored.filter(c => c.passed).length,
    total: scored.length,
  };
}

/**
 * The status the checks add up to, for views that have no result status of their own. It
 * counts the same scored checks as checksSummary, so the two never disagree.
 */
export function checksStatus(
  groups: ResultCheckGroup[]
): TestResultStatus | undefined {
  const checks = groups.flatMap(g => g.checks);
  if (checks.length === 0) return undefined;
  const { passed, total } = countChecks(checks);
  if (passed < total) return 'Fail';
  return total > 0 ? 'Pass' : 'Inconclusive';
}

export function checksSummary(groups: ResultCheckGroup[]): string {
  const { passed, total } = countChecks(groups.flatMap(g => g.checks));
  return `${passed} of ${total} ${total === 1 ? 'check' : 'checks'} passed`;
}

/**
 * "Turn 2" or "Turns 1, 3". Undefined when the check cites no turn, or every turn, since
 * pointing at all of them says nothing about where to look.
 */
export function turnScopeLabel(
  turns: number[],
  turnCount?: number
): string | undefined {
  const unique = [...new Set(turns)].sort((a, b) => a - b);
  if (unique.length === 0) return undefined;
  if (turnCount && turnCount > 1 && unique.length >= turnCount) {
    return undefined;
  }
  return unique.length === 1
    ? `Turn ${unique[0]}`
    : `Turns ${unique.join(', ')}`;
}

/** The groups narrowed to the checks that cite a turn; empty groups are dropped. */
export function checksForTurn(
  groups: ResultCheckGroup[],
  turn: number
): ResultCheckGroup[] {
  return groups
    .map(g => ({
      ...g,
      checks: g.checks.filter(c => c.relevantTurns.includes(turn)),
    }))
    .filter(g => g.checks.length > 0);
}

/**
 * Failed if any check citing the turn failed, passed if only passing ones cite it. A check
 * that cites every turn counts on each of them, so a failure is never hidden from the turns.
 */
export function turnVerdict(
  groups: ResultCheckGroup[],
  turn: number
): 'Pass' | 'Fail' | undefined {
  const { passed, total } = countChecks(
    checksForTurn(groups, turn).flatMap(g => g.checks)
  );
  if (total === 0) return undefined;
  return passed < total ? 'Fail' : 'Pass';
}
