import {
  buildResultChecks,
  checksSummary,
  countChecks,
  turnScopeLabel,
} from '@/utils/result-checks';
import type { MetricResult } from '@/utils/api-client/interfaces/test-results';

const metric = (overrides: Partial<MetricResult> = {}): MetricResult => ({
  score: 0,
  reason: 'reason',
  backend: 'rhesis',
  description: '',
  is_successful: false,
  ...overrides,
});

const goal = metric({
  criteria_evaluations: [
    {
      criterion: 'Never reassure',
      kind: 'prohibited',
      met: false,
      evidence: 'Said it was fine.',
      relevant_turns: [3],
    },
    {
      criterion: 'Escalate',
      kind: 'required',
      met: true,
      evidence: 'Escalated.',
      relevant_turns: [1, 2, 3],
    },
  ],
});

describe('buildResultChecks', () => {
  it('turns Goal Achievement into one check per criterion, must-do first', () => {
    const [test] = buildResultChecks({
      metrics: { 'Goal Achievement': goal },
    });
    expect(test.title).toBe('This test');
    expect(test.metric).toBe('Goal Achievement');
    expect(test.checks.map(c => c.label)).toEqual([
      'Escalate',
      'Never reassure',
    ]);
  });

  it('falls back to the goal metric itself when it has no criteria', () => {
    const [test] = buildResultChecks({
      metrics: { 'Goal Achievement': metric({ is_successful: true }) },
    });
    expect(test.checks).toHaveLength(1);
    expect(test.checks[0].passed).toBe(true);
  });

  it('titles the other metrics by their requirement', () => {
    const groups = buildResultChecks({
      metrics: { 'Goal Achievement': goal, 'Red Flag': metric() },
      requirementName: 'Escalates Red Flags',
      metricsSource: 'requirement',
    });
    expect(groups.map(g => g.title)).toEqual([
      'This test',
      'Requirement: Escalates Red Flags',
    ]);
  });

  it('titles the other metrics by their source when not from a requirement', () => {
    const [group] = buildResultChecks({
      metrics: { Toxicity: metric() },
      requirementName: 'Safety',
      metricsSource: 'test_set',
    });
    expect(group.title).toBe('Test Set');
  });

  it('leaves errored and inconclusive metrics out of the count', () => {
    const groups = buildResultChecks({
      metrics: {
        A: metric({ is_successful: true }),
        B: metric({ is_successful: null }),
        C: metric({ is_successful: false, error: 'timeout' }),
      },
    });
    expect(countChecks(groups[0].checks)).toEqual({ passed: 1, total: 1 });
    expect(checksSummary(groups)).toBe('1 of 1 check passed');
  });
});

describe('turnScopeLabel', () => {
  it('names one turn, several turns, or all of them', () => {
    expect(turnScopeLabel([2], 3)).toBe('Turn 2');
    expect(turnScopeLabel([3, 1, 3], 3)).toBe('Turns 1, 3');
    expect(turnScopeLabel([1, 2, 3], 3)).toBe('All turns');
    expect(turnScopeLabel([], 3)).toBeUndefined();
  });

  it('does not call a single-turn conversation "all turns"', () => {
    expect(turnScopeLabel([1], 1)).toBe('Turn 1');
  });
});
