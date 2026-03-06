import { UsersClient } from '../users-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';

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

describe('UsersClient', () => {
  let client: UsersClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new UsersClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches users and returns data with total from x-total-count header', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'u1' }], 200, { 'x-total-count': '3' })
    );
    const result = await client.getUsers();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/users`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
    expect(result.total).toBe(3);
  });

  it('includes skip and limit in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '0' }));
    await client.getUsers({ skip: 10, limit: 20 });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=10');
    expect(calledUrl).toContain('limit=20');
  });

  it('fetches a single user by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'u1' }));
    await client.getUser('u1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/users/u1'),
      expect.any(Object)
    );
  });

  it('creates a user with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-u' }));
    const payload = { email: 'test@example.com' };
    await client.createUser(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users');
    expect(opts.method).toBe('POST');
  });

  it('updates a user with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'u1' }));
    await client.updateUser('u1', { name: 'Updated Name' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users/u1');
    expect(opts.method).toBe('PUT');
  });

  it('gets user settings at /users/settings', async () => {
    fetchMock.mockResolvedValue(makeFetch({ models: {}, ui: {} }));
    await client.getUserSettings();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/users/settings'),
      expect.any(Object)
    );
  });

  it('updates user settings with PATCH to /users/settings', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ models: {}, ui: { theme: 'dark' } })
    );
    await client.updateUserSettings({ ui: { theme: 'dark' } } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users/settings');
    expect(opts.method).toBe('PATCH');
  });
});
