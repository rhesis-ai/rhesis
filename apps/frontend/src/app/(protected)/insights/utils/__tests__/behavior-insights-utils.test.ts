import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import {
  passRatesToItems,
  resolveEndpointId,
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
    it('puts behaviors with no tests at the bottom', () => {
      const empty = {
        id: '1',
        name: 'Empty',
        overall: { total: 0, passed: 0, failed: 0, pass_rate: 0 },
        metrics: [],
        topics: [],
      };
      const tested = {
        id: '2',
        name: 'Tested',
        overall: { total: 10, passed: 5, failed: 5, pass_rate: 50 },
        metrics: [],
        topics: [],
      };
      const sorted = sortBehaviorColumns([empty, tested]);
      expect(sorted.map(c => c.name)).toEqual(['Tested', 'Empty']);
    });
  });

  describe('passRatesToItems', () => {
    it('converts pass rate map to items', () => {
      const items = passRatesToItems({
        Fluency: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
      });
      expect(items).toHaveLength(1);
      expect(items[0].name).toBe('Fluency');
      expect(items[0].pass_rate).toBe(80);
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
});
