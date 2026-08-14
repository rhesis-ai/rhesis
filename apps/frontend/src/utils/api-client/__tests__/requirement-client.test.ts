import { RequirementClient } from '../requirement-client';
import { API_ENDPOINTS } from '../config';
import { UUID } from 'crypto';

const BASE_URL = 'http://localhost/api/backend';

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

const REQUIREMENT_ID = 'b1b1b1b1-0000-0000-0000-000000000001' as UUID;

describe('RequirementClient', () => {
  let client: RequirementClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new RequirementClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // getRequirements
  // -------------------------------------------------------------------------

  it('fetches requirements with default params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'b1' }]));

    const result = await client.getRequirements();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}${API_ENDPOINTS.requirements}`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes $filter in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getRequirements({ $filter: "name eq 'Safety'" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('%24filter');
  });

  // -------------------------------------------------------------------------
  // getRequirement / getRequirementWithMetrics
  // -------------------------------------------------------------------------

  it('fetches a single requirement by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: REQUIREMENT_ID }));

    await client.getRequirement(REQUIREMENT_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        `${API_ENDPOINTS.requirements}/${REQUIREMENT_ID}`
      ),
      expect.any(Object)
    );
  });

  it('fetches a requirement with metrics (includes=metrics in URL)', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: REQUIREMENT_ID, metrics: [] }));

    await client.getRequirementWithMetrics(REQUIREMENT_ID);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('include=metrics');
  });

  // -------------------------------------------------------------------------
  // getRequirementsWithMetrics
  // -------------------------------------------------------------------------

  it('getRequirementsWithMetrics delegates to getRequirements', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'b1', metrics: [] }]));

    const result = await client.getRequirementsWithMetrics();

    expect(result).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // createRequirement / updateRequirement / deleteRequirement
  // -------------------------------------------------------------------------

  it('creates a requirement with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-b' }));
    const payload = { name: 'New Requirement', description: 'desc' };

    await client.createRequirement(payload as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(API_ENDPOINTS.requirements);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('updates a requirement with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: REQUIREMENT_ID }));

    await client.updateRequirement(REQUIREMENT_ID, {
      name: 'Updated',
    } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`${API_ENDPOINTS.requirements}/${REQUIREMENT_ID}`);
    expect(opts.method).toBe('PUT');
  });

  it('deletes a requirement with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: REQUIREMENT_ID }));

    await client.deleteRequirement(REQUIREMENT_ID);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`${API_ENDPOINTS.requirements}/${REQUIREMENT_ID}`);
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // getRequirementMetrics
  // -------------------------------------------------------------------------

  it('fetches metrics for a requirement', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'm1' }]));

    await client.getRequirementMetrics(REQUIREMENT_ID);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(
      `${API_ENDPOINTS.requirements}/${REQUIREMENT_ID}/metrics/`
    );
    expect(calledUrl).toContain('limit=100');
  });

  it('passes custom skip/limit to getRequirementMetrics', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getRequirementMetrics(REQUIREMENT_ID, { skip: 10, limit: 20 });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=10');
    expect(calledUrl).toContain('limit=20');
  });
});
