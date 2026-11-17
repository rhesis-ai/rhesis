import { act, renderHook } from '@testing-library/react';
import type { ReportDetail } from '@/utils/api-client/interfaces/report';
import { ReportReloadError, useReport } from '../useReport';

const updateReport = jest.fn();
const getReport = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getReportsClient: () => ({ updateReport, getReport }),
  })),
}));

function report(requirementIds: string[]): ReportDetail {
  return {
    id: 'r1',
    title: 'Release 2.5',
    endpoint_id: 'e1',
    status: 'draft',
    result_rule: 'latest',
    is_release: true,
    test_run_ids: [],
    tagged_run_ids: [],
    requirement_ids: requirementIds,
    sections: {},
    permitted_actions: [],
  } as ReportDetail;
}

describe('useReport', () => {
  beforeEach(() => {
    let current = report(['a', 'b', 'c']);
    updateReport.mockReset().mockImplementation(async (_id, body) => {
      current = { ...current, ...body };
    });
    getReport.mockReset().mockImplementation(async () => current);
  });

  it('applies two quick removals one after the other', async () => {
    const { result } = renderHook(() => useReport(report(['a', 'b', 'c'])));
    const drop = (id: string) =>
      result.current.update(r => ({
        requirement_ids: r.requirement_ids.filter(x => x !== id),
      }));

    await act(async () => {
      await Promise.all([drop('a'), drop('b')]);
    });

    expect(updateReport.mock.calls.map(call => call[1])).toEqual([
      { requirement_ids: ['b', 'c'] },
      { requirement_ids: ['c'] },
    ]);
    expect(result.current.report.requirement_ids).toEqual(['c']);
  });

  it('tells a failed reload apart from a failed save', async () => {
    getReport.mockRejectedValueOnce(new Error('network'));
    const { result } = renderHook(() => useReport(report(['a'])));

    await expect(
      act(() => result.current.update({ title: 'New' }))
    ).rejects.toBeInstanceOf(ReportReloadError);
  });

  it('keeps going after a failed save', async () => {
    updateReport.mockRejectedValueOnce(new Error('409'));
    const { result } = renderHook(() => useReport(report(['a'])));

    await act(async () => {
      await result.current.update({ title: 'First' }).catch(() => undefined);
      await result.current.update({ title: 'Second' });
    });

    expect(updateReport).toHaveBeenCalledTimes(2);
    expect(result.current.report.title).toBe('Second');
  });
});
