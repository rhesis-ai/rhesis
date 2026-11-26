import { QueryClient } from '@tanstack/react-query';
import { readFirstPage, writeFirstPage } from '../cache';
import { emptyFilters, firstPageParams, listParams } from '..';
import { tracesList } from '@/app/(protected)/traces/components/list';

const scope = { userId: 'u1', organizationId: 'o1', projectId: 'p1' };
const page = { data: [{ id: 'a' }], totalCount: 1 };

describe('first-page cache', () => {
  it('shares an entry between builds of a list that names itself', () => {
    const client = new QueryClient();
    writeFirstPage(client, { cacheId: 'traces' }, scope, page);

    expect(readFirstPage(client, { cacheId: 'traces' }, scope)).toEqual(page);
  });

  it('keeps two unnamed descriptors apart', () => {
    const client = new QueryClient();
    writeFirstPage(client, {}, scope, page);

    expect(readFirstPage(client, {}, scope)).toBeUndefined();
  });

  it('keeps projects apart', () => {
    const client = new QueryClient();
    writeFirstPage(client, { cacheId: 'traces' }, scope, page);

    expect(
      readFirstPage(
        client,
        { cacheId: 'traces' },
        { ...scope, projectId: 'p2' }
      )
    ).toBeUndefined();
  });

  it("takes the traces page's default view for its first page", () => {
    // The page starts on the "all" time range, which the cache's first page
    // leaves empty; both must ask for the same rows.
    const traces = tracesList('p1');
    const defaultView = listParams(traces, {
      page: 1,
      pageSize: traces.defaultPageSize,
      sort: traces.defaultSort,
      filters: { ...emptyFilters(traces), timeRange: 'all' },
    });

    expect(defaultView).toEqual(firstPageParams(traces));
  });
});
