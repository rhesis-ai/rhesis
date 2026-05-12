import { FeaturesClient } from '../features-client';

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

describe('FeaturesClient', () => {
  let client: FeaturesClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new FeaturesClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('calls GET /features with the session token', async () => {
    const response = {
      license: { edition: 'community', licensed: false },
      enabled: ['sso'],
    };
    fetchMock.mockResolvedValue(makeFetch(response));

    const result = await client.getFeatures();

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/features`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token',
        }),
      })
    );
    expect(result).toEqual(response);
  });

  it('tolerates unknown feature names in the enabled list', async () => {
    const response = {
      license: { edition: 'community', licensed: false },
      enabled: ['sso', 'a_future_feature_we_dont_know_yet'],
    };
    fetchMock.mockResolvedValue(makeFetch(response));

    const result = await client.getFeatures();

    expect(result.enabled).toHaveLength(2);
  });
});
