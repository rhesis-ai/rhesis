import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { InsightsRow } from '@/utils/api-client/interfaces/insights';
import {
  assertInsightsTestRunIdsWithinLimit,
  buildRequirementColumns,
  MAX_INSIGHTS_TEST_RUN_IDS,
  type RequirementInsightColumn,
  resolveEndpointId,
  rowToPassFailStats,
  sortRequirementColumns,
  sortByPassRateAsc,
} from '../requirement-insights-utils';

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

describe('requirement-insights-utils', () => {
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

  describe('sortRequirementColumns', () => {
    it('sorts requirements alphabetically by name', () => {
      const mk = (name: string): RequirementInsightColumn => ({
        id: name,
        name,
        groupBy: 'requirement',
        impact: null,
        children: [],
        overall: { total: 10, passed: 5, failed: 5, pass_rate: 50 },
        metrics: [],
        topics: [],
      });
      const sorted = sortRequirementColumns([
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

    it('puts the "none" group last', () => {
      const none: RequirementInsightColumn = {
        id: null,
        name: 'No impact',
        groupBy: 'impact',
        impact: null,
        children: [],
        overall: { total: 1, passed: 1, failed: 0, pass_rate: 100 },
        metrics: [],
        topics: [],
      };
      const safety = { ...none, id: 'i-1', name: 'Safety', impact: 'Safety' };
      const sorted = sortRequirementColumns([none, safety]);
      expect(sorted.map(c => c.id)).toEqual(['i-1', null]);
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

  describe('buildRequirementColumns', () => {
    const requirementRows: InsightsRow[] = [
      {
        requirement_id: 'b-1',
        requirement: 'Robustness',
        count: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      },
      {
        requirement_id: 'b-2',
        requirement: 'Compliance',
        count: 5,
        passed: 5,
        failed: 0,
        pass_rate: 100,
      },
    ];
    const topicRows: InsightsRow[] = [
      {
        requirement_id: 'b-1',
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
        requirement_id: 'b-1',
        metric: 'Fluency',
        count: 10,
        passed: 8,
        failed: 2,
        pass_rate: 80,
      },
    ];

    it('builds one column per requirement row, sorted alphabetically', () => {
      const columns = buildRequirementColumns(
        requirementRows,
        topicRows,
        metricRows
      );
      expect(columns.map(c => c.name)).toEqual(['Compliance', 'Robustness']);
    });

    it('groups topic/metric rows onto the matching requirement_id', () => {
      const [, robustness] = buildRequirementColumns(
        requirementRows,
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

    it('leaves a requirement with no topic/metric rows empty', () => {
      const [compliance] = buildRequirementColumns(
        requirementRows,
        topicRows,
        metricRows
      );
      expect(compliance.name).toBe('Compliance');
      expect(compliance.topics).toEqual([]);
      expect(compliance.metrics).toEqual([]);
    });

    it('skips rows missing requirement_id or requirement', () => {
      const columns = buildRequirementColumns(
        [
          {
            requirement: 'NoId',
            count: 1,
            passed: 1,
            failed: 0,
            pass_rate: 100,
          },
        ],
        [],
        []
      );
      expect(columns).toEqual([]);
    });

    it('carries the requirement impact for the dot', () => {
      const [column] = buildRequirementColumns(
        [{ ...requirementRows[0], impact_id: 'i-1', impact: 'Safety' }],
        [],
        []
      );
      expect(column.impact).toBe('Safety');
      expect(column.groupBy).toBe('requirement');
    });

    it('groups by impact and keeps the "No impact" group', () => {
      const pass = { count: 2, passed: 1, failed: 1, pass_rate: 50 };
      const columns = buildRequirementColumns(
        [
          { impact_id: null, impact: null, ...pass },
          { impact_id: 'i-1', impact: 'Safety', ...pass },
        ],
        [{ impact_id: null, topic_id: 't-1', topic: 'Billing', ...pass }],
        [{ impact_id: 'i-1', metric: 'Fluency', ...pass }],
        'impact'
      );
      expect(columns.map(c => [c.id, c.name, c.impact])).toEqual([
        ['i-1', 'Safety', 'Safety'],
        [null, 'No impact', null],
      ]);
      expect(columns[0].metrics.map(m => m.name)).toEqual(['Fluency']);
      expect(columns[0].children).toEqual([]);
      expect(columns[1].topics.map(t => t.name)).toEqual(['Billing']);
    });

    it('groups by parent and keeps the "No parent" group', () => {
      const pass = { count: 2, passed: 2, failed: 0, pass_rate: 100 };
      const columns = buildRequirementColumns(
        [
          { requirement_parent_id: null, requirement_parent: null, ...pass },
          {
            requirement_parent_id: 'r-1',
            requirement_parent: 'Refunds',
            ...pass,
          },
        ],
        [],
        [],
        'parent'
      );
      expect(columns.map(c => [c.id, c.name])).toEqual([
        ['r-1', 'Refunds'],
        [null, 'No parent'],
      ]);
    });

    it("lists each parent group's children A–Z", () => {
      const pass = { count: 1, passed: 1, failed: 0, pass_rate: 100 };
      const [refunds] = buildRequirementColumns(
        [
          {
            requirement_parent_id: 'r-1',
            requirement_parent: 'Refunds',
            ...pass,
          },
        ],
        [],
        [],
        'parent',
        [
          { requirement_parent_id: 'r-1', requirement: 'Partial', count: 1 },
          { requirement_parent_id: 'r-1', requirement: 'Full', count: 2 },
          { requirement_parent_id: 'r-2', requirement: 'Other', count: 1 },
        ]
      );
      expect(refunds.children).toEqual(['Full', 'Partial']);
    });

    it('lists each impact group\'s requirements, the "No impact" one too', () => {
      const pass = { count: 1, passed: 1, failed: 0, pass_rate: 100 };
      const columns = buildRequirementColumns(
        [
          { impact_id: 'i-1', impact: 'Safety', ...pass },
          { impact_id: null, impact: null, ...pass },
        ],
        [],
        [],
        'impact',
        [
          { impact_id: 'i-1', requirement: 'Never Diagnoses', count: 1 },
          { impact_id: null, requirement: 'Escalates', count: 1 },
        ]
      );
      expect(columns.map(c => c.children)).toEqual([
        ['Never Diagnoses'],
        ['Escalates'],
      ]);
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
