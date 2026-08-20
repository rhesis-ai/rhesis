import {
  classifyZone,
  flaggedResources,
  findWorstResource,
  isKnownQuotaResource,
  parseQuotaError,
  quotaCopy,
  usageMenuRows,
  zoneColor,
} from '@/utils/quota';
import { QuotaResource } from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

/** `ceiling` defaults to `limit` (a hard tier, no grace band). */
function item(
  used: number,
  limit: number | null,
  options: { kind?: 'flow' | 'stock'; ceiling?: number | null } = {}
): UsageResourceItem {
  const { kind = 'flow', ceiling } = options;
  return {
    used,
    limit,
    ceiling: ceiling === undefined ? limit : ceiling,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    kind,
  };
}

describe('classifyZone', () => {
  it('treats an unlimited resource as healthy at any usage', () => {
    expect(classifyZone(item(10_000_000, null))).toBe('healthy');
  });

  it.each([
    [0, 'healthy'],
    [79, 'healthy'],
    [80, 'approaching'],
    [99, 'approaching'],
    [100, 'blocked'],
    [150, 'blocked'],
  ])('hard tier limit 100: used %i -> %s', (used, expected) => {
    expect(classifyZone(item(used, 100))).toBe(expected);
  });

  it.each([
    [79, 'healthy'],
    [80, 'approaching'],
    [99, 'approaching'],
    [100, 'pastIncluded'],
    [124, 'pastIncluded'],
    [125, 'blocked'],
    [200, 'blocked'],
  ])('soft tier limit 100 ceiling 125: used %i -> %s', (used, expected) => {
    expect(classifyZone(item(used, 100, { ceiling: 125 }))).toBe(expected);
  });

  it('treats a limit of zero as blocked, not unlimited', () => {
    // The backend's rule is `allowed = used < ceiling` and ceiling_for(0) is
    // 0, so such an org is refused from its first request.
    expect(classifyZone(item(0, 0))).toBe('blocked');
  });

  it('treats a null ceiling beside a numeric limit as a hard tier', () => {
    // Not a shape the API emits, but it must not park the resource in
    // pastIncluded and promise an overage allowance that does not exist.
    expect(classifyZone(item(100, 100, { ceiling: null }))).toBe('blocked');
  });
});

describe('zoneColor', () => {
  it('maps each zone to a severity', () => {
    expect(zoneColor('healthy')).toBe('success');
    expect(zoneColor('approaching')).toBe('warning');
    expect(zoneColor('pastIncluded')).toBe('warning');
    expect(zoneColor('blocked')).toBe('error');
  });
});

describe('flaggedResources', () => {
  it('omits healthy resources', () => {
    const flagged = flaggedResources({
      [QuotaResource.TEST_EXECUTIONS]: item(10, 100),
      [QuotaResource.PROJECTS]: item(90, 100, { kind: 'stock' }),
    });
    expect(flagged.map(f => f.resource)).toEqual([QuotaResource.PROJECTS]);
  });

  it('skips a resource the label map does not know about', () => {
    expect(flaggedResources({ some_future_resource: item(99, 100) })).toEqual(
      []
    );
  });

  it('ranks a blocked resource above one deeper into its grace band', () => {
    // The regression this guards: sorting by ratio alone put the soft-tier
    // resource (ratio 1.5, still running) ahead of the hard-blocked one
    // (ratio 1.0), and QuotaBanner shows only the worst -- so an actual
    // block was hidden behind a warning.
    const worst = findWorstResource({
      [QuotaResource.TEST_EXECUTIONS]: item(150, 100, { ceiling: 200 }),
      [QuotaResource.PROJECTS]: item(1, 1, { kind: 'stock' }),
    });
    expect(worst?.resource).toBe(QuotaResource.PROJECTS);
    expect(worst?.zone).toBe('blocked');
  });

  it('falls back to ratio within the same zone', () => {
    const flagged = flaggedResources({
      [QuotaResource.TEST_EXECUTIONS]: item(80, 100),
      [QuotaResource.TEST_GENERATION]: item(95, 100),
    });
    expect(flagged.map(f => f.resource)).toEqual([
      QuotaResource.TEST_GENERATION,
      QuotaResource.TEST_EXECUTIONS,
    ]);
  });

  it('returns null from findWorstResource when nothing is flagged', () => {
    expect(findWorstResource({ [QuotaResource.PROJECTS]: item(1, 100) })).toBe(
      null
    );
  });
});

describe('quotaCopy', () => {
  const base = { used: 80, limit: 100, canUpgrade: true } as const;

  it('names the organization as the subject, never the reader', () => {
    const { sentence } = quotaCopy({
      ...base,
      resource: QuotaResource.TEST_EXECUTIONS,
      kind: 'flow',
      zone: 'approaching',
    });
    expect(sentence).toBe(
      'Your organization has used 80% of its test runs for this period.'
    );
    expect(sentence).not.toMatch(/\byou(r)?\b(?! organization)/i);
  });

  it('counts a stock resource instead of percentaging it', () => {
    expect(
      quotaCopy({
        ...base,
        used: 4,
        limit: 5,
        resource: QuotaResource.PROJECTS,
        kind: 'stock',
        zone: 'approaching',
      }).sentence
    ).toBe('Your organization is using 4 of 5 projects.');
  });

  it('says nothing is blocked yet in the grace band', () => {
    const { sentence, recourse } = quotaCopy({
      ...base,
      used: 110,
      resource: QuotaResource.TEST_EXECUTIONS,
      kind: 'flow',
      zone: 'pastIncluded',
    });
    expect(sentence).toBe(
      'Your organization is past its included test runs for this period.'
    );
    expect(recourse).toBe(
      'You can keep running until the overage allowance runs out.'
    );
  });

  it('gives a blocked flow resource its reset date', () => {
    const { sentence, recourse } = quotaCopy({
      resource: QuotaResource.TEST_EXECUTIONS,
      kind: 'flow',
      used: 1000,
      limit: 1000,
      zone: 'blocked',
      periodEnd: '2026-08-31',
      canUpgrade: true,
    });
    expect(sentence).toBe(
      'Your organization is at its test runs limit for this period (1,000 of 1,000).'
    );
    expect(recourse).toBe('Resets 31 Aug. Upgrade to raise this limit.');
  });

  it('points a member at an admin instead of at the upgrade link', () => {
    expect(
      quotaCopy({
        resource: QuotaResource.TEST_EXECUTIONS,
        kind: 'flow',
        used: 1000,
        limit: 1000,
        zone: 'blocked',
        periodEnd: '2026-08-31',
        canUpgrade: false,
      }).recourse
    ).toBe('Resets 31 Aug. Ask an org admin to raise this limit.');
  });

  it('names the freeing action for a blocked stock resource', () => {
    expect(
      quotaCopy({
        resource: QuotaResource.PROJECTS,
        kind: 'stock',
        used: 1,
        limit: 1,
        zone: 'blocked',
        canUpgrade: true,
      })
    ).toEqual({
      sentence: 'Your organization is at its projects limit (1 of 1).',
      recourse: 'Delete a project or upgrade to add more.',
    });
  });

  it('always offers a next step on a legacy 402 with no kind', () => {
    // The regression this guards: the admin branch returned an empty
    // recourse, so the only person who could act saw no next step.
    for (const canUpgrade of [true, false]) {
      const { recourse } = quotaCopy({
        resource: QuotaResource.PROJECTS,
        kind: undefined,
        used: 1,
        limit: 1,
        zone: 'blocked',
        canUpgrade,
      });
      expect(recourse).not.toBe('');
    }
  });
});

describe('parseQuotaError', () => {
  function quota402(data: Record<string, unknown>) {
    const err = new Error('API error: 402 - quota') as Error & {
      status?: number;
      data?: Record<string, unknown>;
    };
    err.status = 402;
    err.data = data;
    return err;
  }

  it('reads the widened 402 body', () => {
    expect(
      parseQuotaError(
        quota402({
          error: 'quota_exceeded',
          resource: 'test_executions',
          used: 100,
          limit: 100,
          kind: 'flow',
          period_end: '2026-08-31',
          message: 'nope',
        })
      )
    ).toEqual({
      resource: 'test_executions',
      used: 100,
      limit: 100,
      kind: 'flow',
      periodEnd: '2026-08-31',
      message: 'nope',
    });
  });

  it('tolerates a legacy body with no kind or period_end', () => {
    const parsed = parseQuotaError(
      quota402({
        error: 'quota_exceeded',
        resource: 'projects',
        used: 1,
        limit: 1,
      })
    );
    expect(parsed?.kind).toBeUndefined();
    expect(parsed?.periodEnd).toBeUndefined();
  });

  it('ignores a 402 that is not a quota error', () => {
    expect(parseQuotaError(quota402({ error: 'something_else' }))).toBe(null);
  });

  it('ignores non-402 errors and non-errors', () => {
    const err = new Error('boom') as Error & { status?: number };
    err.status = 500;
    expect(parseQuotaError(err)).toBe(null);
    expect(parseQuotaError('not an error')).toBe(null);
    expect(parseQuotaError(null)).toBe(null);
  });
});

describe('isKnownQuotaResource', () => {
  it('accepts a wire value the label map knows', () => {
    expect(isKnownQuotaResource('test_executions')).toBe(true);
  });

  it('rejects one it does not', () => {
    expect(isKnownQuotaResource('some_future_resource')).toBe(false);
  });
});

describe('usageMenuRows', () => {
  const order = [
    QuotaResource.TEST_EXECUTIONS,
    QuotaResource.TRACING_SPANS,
    QuotaResource.TEST_GENERATION,
    QuotaResource.MODEL_TOKENS,
    QuotaResource.SEATS,
    QuotaResource.PROJECTS,
    QuotaResource.ENDPOINTS,
  ] as const;

  it('pads a healthy org up to the minimum', () => {
    const rows = usageMenuRows(
      {
        [QuotaResource.TEST_EXECUTIONS]: item(1, 100),
        [QuotaResource.SEATS]: item(1, 10, { kind: 'stock' }),
        [QuotaResource.PROJECTS]: item(1, 5, { kind: 'stock' }),
        [QuotaResource.ENDPOINTS]: item(1, 5, { kind: 'stock' }),
      },
      order,
      3
    );
    expect(rows).toHaveLength(3);
    expect(rows.every(r => r.zone === 'healthy')).toBe(true);
  });

  it('never caps, so the row count always matches the badge', () => {
    // Five flagged resources must produce five rows even though the floor
    // is three, or the block and the badge disagree.
    const rows = usageMenuRows(
      {
        [QuotaResource.TEST_EXECUTIONS]: item(100, 100),
        [QuotaResource.TRACING_SPANS]: item(100, 100),
        [QuotaResource.TEST_GENERATION]: item(100, 100),
        [QuotaResource.SEATS]: item(10, 10, { kind: 'stock' }),
        [QuotaResource.PROJECTS]: item(5, 5, { kind: 'stock' }),
      },
      order,
      3
    );
    expect(rows).toHaveLength(5);
  });

  it('puts flagged resources first, worst first', () => {
    const rows = usageMenuRows(
      {
        [QuotaResource.TEST_EXECUTIONS]: item(1, 100),
        [QuotaResource.PROJECTS]: item(5, 5, { kind: 'stock' }),
        [QuotaResource.SEATS]: item(8, 10, { kind: 'stock' }),
      },
      order,
      3
    );
    expect(rows[0].resource).toBe(QuotaResource.PROJECTS);
    expect(rows[0].zone).toBe('blocked');
    expect(rows[1].resource).toBe(QuotaResource.SEATS);
    expect(rows[1].zone).toBe('approaching');
  });

  it('does not pad with an unlimited resource', () => {
    // "Model Tokens unlimited" is a row that tells the reader nothing.
    const rows = usageMenuRows(
      {
        [QuotaResource.MODEL_TOKENS]: item(999, null),
        [QuotaResource.SEATS]: item(1, 10, { kind: 'stock' }),
      },
      order,
      3
    );
    expect(rows.map(r => r.resource)).toEqual([QuotaResource.SEATS]);
  });
});
