import {
  buildTurnFindings,
  turnStatus,
  turnHasConversationFindings,
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
      Unsure: metric({ is_successful: null, relevant_turns: [1] }),
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

  it('promotes findings citing every turn to conversation-level', () => {
    const allTurns = buildTurnFindings(
      {
        all_criteria_met: false,
        reason: '',
        evidence: [],
        criteria_evaluations: [
          {
            criterion: 'Stay on topic',
            kind: 'required',
            met: false,
            evidence: 'Went off-topic throughout',
            relevant_turns: [1, 2, 3],
          },
          {
            criterion: 'Be polite',
            kind: 'required',
            met: true,
            evidence: 'Polite in turn 2',
            relevant_turns: [2],
          },
        ],
      },
      {
        'Goal Achievement': metric({ is_successful: false }),
        'OWASP LLM01': metric({
          is_successful: true,
          relevant_turns: [1, 2, 3],
        }),
      },
      3
    );

    // "Stay on topic" cites all 3 turns → promoted, keeps relevant_turns for the indicator
    const stayOnTopic = allTurns.find(f => f.label === 'Stay on topic');
    expect(stayOnTopic?.conversationLevel).toBe(true);
    expect(stayOnTopic?.relevant_turns).toEqual([1, 2, 3]);

    // "Be polite" only cites turn 2 → stays per-turn
    expect(allTurns.find(f => f.label === 'Be polite')?.conversationLevel).toBeUndefined();

    // OWASP metric cites all 3 turns → promoted
    expect(allTurns.find(f => f.metric === 'OWASP LLM01')?.conversationLevel).toBe(true);

    // Per-turn status: turn 1 has no per-turn findings, turn 2 passes from "Be polite"
    expect(turnStatus(allTurns, 1)).toBeUndefined();
    expect(turnStatus(allTurns, 2)).toBe('Pass');

    // Soft indicator: turns 1-3 were cited by conversation-level findings
    expect(turnHasConversationFindings(allTurns, 1)).toBe(true);
    expect(turnHasConversationFindings(allTurns, 2)).toBe(true);
    expect(turnHasConversationFindings(allTurns, 3)).toBe(true);

    // Promoted failures show as uncited
    const uncited = uncitedFailures(allTurns);
    expect(uncited.map(f => f.label)).toEqual(['Stay on topic']);
  });
});
