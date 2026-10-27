import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { automatedVerdictFor } from '../trace-verdict';

function spanWith(metrics: Record<string, unknown>): SpanNode {
  return {
    trace_metrics: { turn_metrics: { metrics } },
  } as unknown as SpanNode;
}

describe('automatedVerdictFor', () => {
  it('leaves out a metric whose target matched nothing in the trace', () => {
    const verdict = automatedVerdictFor(
      spanWith({
        relevance: { is_successful: true },
        refunds: { is_successful: null, not_applicable: true },
      })
    );

    expect(verdict).toEqual({
      passed: true,
      label: 'Passed',
      count: '1/1',
      failed: 0,
    });
  });

  it('has no verdict when no metric applied', () => {
    const verdict = automatedVerdictFor(
      spanWith({ refunds: { is_successful: null, not_applicable: true } })
    );

    expect(verdict).toBeNull();
  });
});
