import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { PaginatedResponse } from '@/utils/api-client/interfaces/pagination';
import { resetProjectNameCache, withProjectNames } from '../list';
import type { AuditEvent } from '../types';

function factory(getProjects: jest.Mock): ApiClientFactory {
  return {
    getProjectsClient: () => ({ getProjects }),
  } as unknown as ApiClientFactory;
}

function page(projectIds: (string | null)[]): PaginatedResponse<AuditEvent> {
  return {
    data: projectIds.map(
      (project_id, i) => ({ id: `e${i}`, project_id }) as AuditEvent
    ),
    pagination: {
      totalCount: projectIds.length,
      skip: 0,
      limit: 25,
      currentPage: 0,
      pageSize: 25,
      totalPages: 1,
    },
  };
}

describe('withProjectNames', () => {
  beforeEach(() => resetProjectNameCache());

  it('looks up each project on the page once, in one call', async () => {
    const getProjects = jest.fn().mockResolvedValue({
      data: [{ id: 'p1', name: 'Travel Assistant' }],
    });
    const result = await withProjectNames(
      factory(getProjects),
      page(['p1', 'p1', 'p2', null])
    );
    expect(getProjects).toHaveBeenCalledTimes(1);
    expect(getProjects).toHaveBeenCalledWith({
      limit: 2,
      $filter: "id eq 'p1' or id eq 'p2'",
    });
    expect(result.data.map(e => e.project_name)).toEqual([
      'Travel Assistant',
      'Travel Assistant',
      undefined,
      undefined,
    ]);
  });

  it('asks only for projects it has not named yet', async () => {
    const getProjects = jest
      .fn()
      .mockResolvedValue({ data: [{ id: 'p1', name: 'Travel Assistant' }] });
    await withProjectNames(factory(getProjects), page(['p1']));
    await withProjectNames(factory(getProjects), page(['p1']));
    expect(getProjects).toHaveBeenCalledTimes(1);
  });

  it('makes no call for a page of org-level events', async () => {
    const getProjects = jest.fn();
    await withProjectNames(factory(getProjects), page([null, null]));
    expect(getProjects).not.toHaveBeenCalled();
  });

  it('keeps the page when the lookup fails', async () => {
    const getProjects = jest.fn().mockRejectedValue(new Error('403'));
    const result = await withProjectNames(factory(getProjects), page(['p1']));
    expect(result.data[0].project_name).toBeUndefined();
  });
});
