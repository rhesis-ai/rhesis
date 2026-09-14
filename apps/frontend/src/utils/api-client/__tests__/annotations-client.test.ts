import { AnnotationsClient } from '../annotations-client';

function makeFetch(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (k: string) => headers[k.toLowerCase()] ?? null,
      entries: () => Object.entries(headers),
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

describe('AnnotationsClient', () => {
  let client: AnnotationsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new AnnotationsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  it('creates an annotation with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'ann1' }));

    await client.createAnnotation({
      entity_type: 'TestResult',
      entity_id: 'r1',
      status_id: 'status-id',
      comments: 'Looks good',
    });

    const [url, opts] = fetchMock.mock.calls[0];
    // joinUrl strips the trailing slash, so this lands on /annotations and the
    // backend redirects to /annotations/ with the method and body intact. Same
    // as every other create in this codebase.
    expect(url).toContain('/annotations');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.entity_type).toBe('TestResult');
    expect(body.entity_id).toBe('r1');
    expect(body.status_id).toBe('status-id');
    expect(body.comments).toBe('Looks good');
  });

  it('sends the target when one is given', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'ann1' }));

    const target = { type: 'metric' as const, reference: 'm1' };
    await client.createAnnotation({
      entity_type: 'TestResult',
      entity_id: 'r1',
      status_id: 's1',
      comments: 'notes',
      target,
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body).target).toEqual(target);
  });

  it('updates an annotation with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'ann1' }));

    await client.updateAnnotation('ann1', { comments: 'Updated' });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/annotations/ann1');
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body).comments).toBe('Updated');
  });

  it('deletes an annotation with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'ann1' }));

    await client.deleteAnnotation('ann1');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/annotations/ann1');
    expect(opts.method).toBe('DELETE');
  });

  it('fetches every annotation on one entity', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'ann1' }]));

    await client.getByEntity('Trace', 't1');

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/annotations/entity/Trace/t1');
  });

  it('keeps resolved=false, which is a real filter rather than an omission', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '0' }));

    await client.getAnnotations({ resolved: false, test_run_id: 'run1' });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('resolved=false');
    expect(url).toContain('test_run_id=run1');
  });
});
