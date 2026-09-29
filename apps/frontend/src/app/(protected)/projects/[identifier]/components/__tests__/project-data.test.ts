import type { UUID } from 'crypto';
import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { fetchProjectTraceMetrics } from '../project-data';

const SINGLE: UUID = '00000000-0000-4000-8000-000000000001';
const MULTI: UUID = '00000000-0000-4000-8000-000000000002';
const GONE: UUID = '00000000-0000-4000-8000-000000000003';

function factoryReturning(
  byId: Record<string, Partial<MetricDetail> | Error>
): ApiClientFactory {
  const getMetric = jest.fn(async (id: string) => {
    const found = byId[id];
    if (found instanceof Error) throw found;
    return found as MetricDetail;
  });
  return {
    getMetricsClient: () => ({ getMetric }),
  } as unknown as ApiClientFactory;
}

describe('fetchProjectTraceMetrics', () => {
  it('returns every assigned metric, whatever its scope', async () => {
    const factory = factoryReturning({
      [SINGLE]: { id: SINGLE, metric_scope: ['Single-Turn'] },
      [MULTI]: { id: MULTI, metric_scope: ['Multi-Turn'] },
    });

    const metrics = await fetchProjectTraceMetrics(factory, [SINGLE, MULTI]);

    expect(metrics.map(m => m.id)).toEqual([SINGLE, MULTI]);
  });

  it('drops metrics that no longer load', async () => {
    const factory = factoryReturning({
      [SINGLE]: { id: SINGLE, metric_scope: ['Single-Turn'] },
      [GONE]: new Error('404'),
    });

    const metrics = await fetchProjectTraceMetrics(factory, [SINGLE, GONE]);

    expect(metrics.map(m => m.id)).toEqual([SINGLE]);
  });

  it('makes no request when nothing is assigned', async () => {
    const getMetricsClient = jest.fn();
    const factory = { getMetricsClient } as unknown as ApiClientFactory;

    expect(await fetchProjectTraceMetrics(factory, [])).toEqual([]);
    expect(getMetricsClient).not.toHaveBeenCalled();
  });
});
