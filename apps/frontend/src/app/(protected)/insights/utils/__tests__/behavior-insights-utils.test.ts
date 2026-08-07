import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { InsightsRow } from '@/utils/api-client/interfaces/insights';
import {
  assertInsightsTestRunIdsWithinLimit,
  buildBehaviorColumns,
  MAX_INSIGHTS_TEST_RUN_IDS,
  resolveEndpointId,
  rowToPassFailStats,
  sortBehaviorColumns,
  sortByPassRateAsc,
} from '../behavior-insights-utils';

jest.mock('@/utils/insights-endpoint', () => ({
  readInsightsEndpointId: jest.fn(),
  writeInsightsEndpointId: jest.fn(),
}));

import {
  readInsightsEndpointId,
  writeInsightsEndpointId,
} from '@/utils/insights-endpoint';

const mockedRead = readInsightsEndpointId as jest.Mock;
const mockedWrite = writeInsightsEndpointId as jest.Mock;

describe('behavior-insights-utils', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('sortByPassRateAsc', () => {
    it('sorts by pass rate ascending with zero-test items last', () => {
      const sorted = sortByPassRateAsc([
        { name: 'a', pass_rate: 80, total: 10 },
        { name: 'b', pass_rate: 20, total: 5 },
        { name: 'c', pass_rate: 0, total: 0 },
        { name: 'd', pass_rate: 50, total: 8 },
      ]);
      expect(sorted.map(i => i.name)).toEqual(['b', 'd', 'a', 'c']);
    });
  });

  describe('sortBehaviorColumns', () => {
    it('sorts behaviors alphabetically by name', () => {
      const mk = (name: string) => ({
        id: name,
        name,
        overall: { total: 10, passed: 5, failed: 5, pass_rate: 50 },
        metrics: [],
        topics: [],
      });
      const sorted = sortBehaviorColumns([
        mk('Robustness'),
        mk('Compliance'),
        mk('Garak'),
        mk('Reliability'),
      ]);
      expect(sorted.map(c => c.name)).toEqual([
        'Compliance',
        'Garak',
        'Reliability',
        'Robustness',
      ]);
    });
  });

  describe('rowToPassFailStats', () => {
    it('maps an insights row to PassFailStats', () => {
      const stats = rowToPassFailStats({
        count: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      });
      expect(stats).toEqual({ total: 10, passed: 8, failed: 2, pass_rate: 80 });
    });

    it('defaults missing measures to zero', () => {
      expect(rowToPassFailStats({})).toEqual({
        total: 0,
        passed: 0,
        failed: 0,
        pass_rate: 0,
      });
    });

    it('derives total from passed + failed, not the row count, so errored/pending results are excluded', () => {
      const stats = rowToPassFailStats({
        count: 5,
        passed: 0,
        failed: 2,
        pass_rate: 0,
      });
      expect(stats).toEqual({ total: 2, passed: 0, failed: 2, pass_rate: 0 });
    });
  });

  describe('buildBehaviorColumns', () => {
    const behaviorRows: InsightsRow[] = [
      {
        behavior_id: 'b-1',
        behavior: 'Robustness',
        count: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      },
      {
        behavior_id: 'b-2',
        behavior: 'Compliance',
        count: 5,
        passed: 5,
        failed: 0,
        pass_rate: 100,
      },
    ];
    const topicRows: InsightsRow[] = [
      {
        behavior_id: 'b-1',
        topic_id: 't-1',
        topic: 'Safety',
        count: 6,
        passed: 4,
        failed: 2,
        pass_rate: 66.67,
      },
    ];
    const metricRows: InsightsRow[] = [
      {
        behavior_id: 'b-1',
        metric_name: 'Fluency',
        count: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      },
    ];

    it('builds one column per behavior row, sorted alphabetically', () => {
      const columns = buildBehaviorColumns(behaviorRows, topicRows, metricRows);
      expect(columns.map(c => c.name)).toEqual(['Compliance', 'Robustness']);
    });

    it('groups topic/metric rows onto the matching behavior_id', () => {
      const [, robustness] = buildBehaviorColumns(
        behaviorRows,
        topicRows,
        metricRows
      );
      expect(robustness.id).toBe('b-1');
      expect(robustness.overall).toEqual({
        total: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      });
      expect(robustness.topics).toEqual([
        {
          id: 't-1',
          name: 'Safety',
          total: 6,
          passed: 4,
          failed: 2,
          pass_rate: 66.67,
        },
      ]);
      expect(robustness.metrics).toEqual([
        { name: 'Fluency', total: 10, passed: 8, failed: 2, pass_rate: 80 },
      ]);
    });

    it('leaves a behavior with no topic/metric rows empty', () => {
      const [compliance] = buildBehaviorColumns(
        behaviorRows,
        topicRows,
        metricRows
      );
      expect(compliance.name).toBe('Compliance');
      expect(compliance.topics).toEqual([]);
      expect(compliance.metrics).toEqual([]);
    });

    it('skips rows missing behavior_id or behavior', () => {
      const columns = buildBehaviorColumns(
        [{ behavior: 'NoId', count: 1, passed: 1, failed: 0, pass_rate: 100 }],
        [],
        []
      );
      expect(columns).toEqual([]);
    });
  });

  describe('resolveEndpointId', () => {
    const endpoints: Endpoint[] = [
      {
        id: 'ep-1',
        name: 'One',
        project_id: 'project-1',
        connection_type: 'REST',
        environment: 'development',
        config_source: 'manual',
        response_format: 'json',
      },
      {
        id: 'ep-2',
        name: 'Two',
        project_id: 'project-1',
        connection_type: 'REST',
        environment: 'development',
        config_source: 'manual',
        response_format: 'json',
      },
    ];

    it('returns cookie endpoint when valid for project', () => {
      mockedRead.mockReturnValue('ep-2');
      expect(resolveEndpointId([...endpoints], 'project-1')).toBe('ep-2');
      expect(mockedWrite).not.toHaveBeenCalled();
    });

    it('falls back to first project endpoint and writes cookie', () => {
      mockedRead.mockReturnValue(null);
      expect(resolveEndpointId([...endpoints], 'project-1')).toBe('ep-1');
      expect(mockedWrite).toHaveBeenCalledWith('ep-1');
    });

    it('returns null when no endpoints in project', () => {
      expect(resolveEndpointId([...endpoints], 'other-project')).toBeNull();
    });

    it('matches project id when types differ', () => {
      mockedRead.mockReturnValue(null);
      const numericProjectEndpoints: Endpoint[] = [
        {
          ...endpoints[0],
          project_id: 42 as unknown as string,
        },
      ];
      expect(resolveEndpointId(numericProjectEndpoints, '42')).toBe('ep-1');
    });
  });

  describe('assertInsightsTestRunIdsWithinLimit', () => {
    it('allows selections at or below the cap', () => {
      expect(() =>
        assertInsightsTestRunIdsWithinLimit(
          Array.from(
            { length: MAX_INSIGHTS_TEST_RUN_IDS },
            (_, i) => `run-${i}`
          )
        )
      ).not.toThrow();
    });

    it('throws when the allowlist exceeds the cap', () => {
      expect(() =>
        assertInsightsTestRunIdsWithinLimit(
          Array.from(
            { length: MAX_INSIGHTS_TEST_RUN_IDS + 1 },
            (_, i) => `run-${i}`
          )
        )
      ).toThrow(/Too many test runs/);
    });
  });
});
