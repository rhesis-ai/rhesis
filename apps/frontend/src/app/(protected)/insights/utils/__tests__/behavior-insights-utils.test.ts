import {
  passRatesToItems,
  resolveEndpointId,
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
    it('sorts by pass rate ascending (worst first)', () => {
      const sorted = sortByPassRateAsc([
        { name: 'a', pass_rate: 80 },
        { name: 'b', pass_rate: 20 },
        { name: 'c', pass_rate: 50 },
      ]);
      expect(sorted.map(i => i.name)).toEqual(['b', 'c', 'a']);
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
    const endpoints = [
      { id: 'ep-1', name: 'One', project_id: 'project-1' },
      { id: 'ep-2', name: 'Two', project_id: 'project-1' },
    ] as const;

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
  });
});
