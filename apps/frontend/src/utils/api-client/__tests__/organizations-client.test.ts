import { OrganizationsClient } from '../organizations-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const ORG_ID = 'o1o1o1o1-0000-0000-0000-000000000001';

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

describe('OrganizationsClient', () => {
  let client: OrganizationsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new OrganizationsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches all organizations', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'org-1' }]));
    const result = await client.getOrganizations();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/organizations`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('fetches a single organization by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: ORG_ID }));
    await client.getOrganization(ORG_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/organizations/${ORG_ID}`),
      expect.any(Object)
    );
  });

  it('creates an organization with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-org' }));
    const payload = { name: 'Test Org', owner_id: 'u1', user_id: 'u1' };
    await client.createOrganization(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/organizations');
    expect(opts.method).toBe('POST');
  });

  it('re-throws createOrganization error with detail message from response', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ detail: 'Organization already exists' }, 400, {
        'content-type': 'application/json',
      })
    );
    await expect(
      client.createOrganization({
        name: 'Test Org',
        owner_id: 'u1',
        user_id: 'u1',
      } as never)
    ).rejects.toThrow('Organization already exists');
  });

  it('updates an organization with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: ORG_ID }));
    await client.updateOrganization(ORG_ID, { name: 'Updated Org' });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/organizations/${ORG_ID}`);
    expect(opts.method).toBe('PUT');
  });

  it('loads initial data for an organization with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ status: 'ok', message: 'Loaded' }));
    await client.loadInitialData(ORG_ID);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/organizations/${ORG_ID}/load-initial-data`);
    expect(opts.method).toBe('POST');
  });
});
