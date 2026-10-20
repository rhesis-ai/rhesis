import {
  buildResultChecks,
  checksForTurn,
  checksSummary,
  countChecks,
  turnScopeLabel,
  turnVerdict,
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
  it('names the turns a check cites', () => {
    expect(turnScopeLabel([2], 3)).toBe('Turn 2');
    expect(turnScopeLabel([3, 1, 3], 3)).toBe('Turns 1, 3');
  });

  it('gives no label to a check citing no turn or every turn', () => {
    expect(turnScopeLabel([], 3)).toBeUndefined();
    expect(turnScopeLabel([1, 2, 3], 3)).toBeUndefined();
  });

  it('labels the only turn of a one-turn conversation', () => {
    expect(turnScopeLabel([1], 1)).toBe('Turn 1');
  });
});

describe('turn checks', () => {
  const groups = buildResultChecks({
    metrics: {
      'Goal Achievement': metric({
        is_successful: true,
        criteria_evaluations: [
          {
            criterion: 'Escalates',
            kind: 'required',
            met: true,
            evidence: 'Turn 3',
            relevant_turns: [3],
          },
        ],
      }),
      'Red Flag Escalation': metric({ relevant_turns: [2, 3] }),
      Crashed: metric({ error: 'timeout', relevant_turns: [1] }),
      Unsure: metric({ is_successful: null, relevant_turns: [1] }),
    },
  });

  it('fails a turn any failed check cites, even if a passing one cites it too', () => {
    expect(turnVerdict(groups, 3)).toBe('Fail');
    expect(turnVerdict(groups, 2)).toBe('Fail');
  });

  it('gives no verdict to a turn only unscored checks cite', () => {
    expect(turnVerdict(groups, 1)).toBeUndefined();
    expect(turnVerdict(groups, 4)).toBeUndefined();
  });

  it('keeps only the groups and checks that cite the turn', () => {
    const turn3 = checksForTurn(groups, 3);
    expect(turn3.map(g => g.key)).toEqual(['test', 'metrics']);
    expect(turn3[1].checks.map(c => c.label)).toEqual(['Red Flag Escalation']);
    expect(checksForTurn(groups, 4)).toEqual([]);
  });

  it('uses goal_evaluation criteria when the run has no goal metric entry', () => {
    const [test] = buildResultChecks({
      goalEvaluation: {
        all_criteria_met: false,
        reason: '',
        evidence: [],
        criteria_evaluations: [
          {
            criterion: 'Stay on topic',
            kind: 'required',
            met: false,
            evidence: '',
            relevant_turns: [1, 2],
          },
        ],
      },
    });
    expect(test.metric).toBe('Goal Achievement');
    expect(turnVerdict([test], 2)).toBe('Fail');
  });

  it('prefers the criteria a re-score stored on the goal metric', () => {
    const [test] = buildResultChecks({
      metrics: {
        'Goal Achievement': metric({
          criteria_evaluations: [
            {
              criterion: 'Re-score',
              kind: 'required',
              met: true,
              evidence: '',
              relevant_turns: [],
            },
          ],
        }),
      },
      goalEvaluation: {
        all_criteria_met: false,
        reason: '',
        evidence: [],
        criteria_evaluations: [
          {
            criterion: 'Live run',
            kind: 'required',
            met: false,
            evidence: '',
            relevant_turns: [],
          },
        ],
      },
    });
    expect(test.checks.map(c => c.label)).toEqual(['Re-score']);
  });
});
