import {
  buildTurnFindings,
  turnStatus,
  uncitedFailures,
} from '@/utils/turn-findings';
import type { MetricResult } from '@/utils/api-client/interfaces/test-results';

const metric = (overrides: Partial<MetricResult>): MetricResult => ({
  score: 0,
  reason: 'reason',
  backend: 'rhesis',
  description: '',
  is_successful: false,
  ...overrides,
});

describe('turn findings', () => {
  const findings = buildTurnFindings(
    {
      all_criteria_met: true,
      reason: '',
      evidence: [],
      criteria_evaluations: [
        {
          criterion: 'Escalates',
          kind: 'required',
          met: true,
          evidence: 'Turn 3',
          relevant_turns: [3],
        },
      ],
    },
    {
      'Goal Achievement': metric({ is_successful: true }),
      'Red Flag Escalation': metric({ relevant_turns: [2, 3] }),
      Tone: metric({}),
      Crashed: metric({ error: 'timeout', relevant_turns: [1] }),
      Unsure: metric({
        is_successful: null as unknown as boolean,
        relevant_turns: [1],
      }),
    }
  );

  it('names Goal Achievement criteria after the goal metric', () => {
    expect(findings[0]).toMatchObject({
      metric: 'Goal Achievement',
      label: 'Escalates',
    });
  });

  it('leaves out the goal metric itself, errors and inconclusive metrics', () => {
    expect(findings.map(f => f.metric)).toEqual([
      'Goal Achievement',
      'Red Flag Escalation',
      'Tone',
    ]);
  });

  it('fails a turn any failed finding cites, even if a passing one cites it too', () => {
    expect(turnStatus(findings, 3)).toBe('Fail');
    expect(turnStatus(findings, 2)).toBe('Fail');
  });

  it('gives no status to a turn nothing cites', () => {
    expect(turnStatus(findings, 1)).toBeUndefined();
  });

  it('lists failures that cite no turn', () => {
    expect(uncitedFailures(findings).map(f => f.metric)).toEqual(['Tone']);
  });

  it('prefers the criteria a re-score stored on the goal metric', () => {
    const rescored = buildTurnFindings(
      {
        all_criteria_met: true,
        reason: '',
        evidence: [],
        criteria_evaluations: [
          {
            criterion: 'Live run',
            kind: 'required',
            met: true,
            evidence: '',
            relevant_turns: [1],
          },
        ],
      },
      {
        'Goal Achievement': metric({
          criteria_evaluations: [
            {
              criterion: 'Re-score',
              kind: 'required',
              met: false,
              evidence: '',
              relevant_turns: [1],
            },
          ],
        }),
      }
    );
    expect(rescored.map(f => f.label)).toEqual(['Re-score']);
  });
});
