import { GarakClient } from '../garak-client';

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

describe('GarakClient', () => {
  let client: GarakClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new GarakClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('lists probe modules at GET /garak/probes', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ garak_version: '0.9', modules: [], total_modules: 0 })
    );
    const result = await client.listProbeModules();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/garak/probes`),
      expect.any(Object)
    );
    expect(result.garak_version).toBe('0.9');
  });

  it('gets probe module detail', async () => {
    fetchMock.mockResolvedValue(makeFetch({ name: 'atkgen', probes: [] }));
    await client.getProbeModuleDetail('atkgen');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/garak/probes/atkgen'),
      expect.any(Object)
    );
  });

  it('previews import with POST to /garak/import/preview', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        garak_version: '0.9',
        total_test_sets: 1,
        total_tests: 5,
        detector_count: 0,
        detectors: [],
        probes: [],
      })
    );
    const request = {
      probes: [{ module_name: 'atkgen', class_name: 'AtkGen' }],
    };
    await client.previewImport(request);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/garak/import/preview');
    expect(opts.method).toBe('POST');
  });

  it('imports probes with POST to /garak/import', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        test_sets: [],
        total_test_sets: 0,
        total_tests: 0,
        garak_version: '0.9',
      })
    );
    const request = {
      probes: [{ module_name: 'atkgen', class_name: 'AtkGen' }],
    };
    await client.importProbes(request);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/garak/import');
    expect(opts.method).toBe('POST');
  });

  it('previews sync for a test set', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        can_sync: true,
        old_version: '0.8',
        new_version: '0.9',
        to_add: 2,
        to_remove: 0,
        unchanged: 5,
        last_synced_at: null,
      })
    );
    await client.previewSync('test-set-id');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/garak/sync/test-set-id/preview'),
      expect.any(Object)
    );
  });

  it('syncs a test set with POST to /garak/sync/:id', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        added: 2,
        removed: 0,
        unchanged: 5,
        new_garak_version: '0.9',
        old_garak_version: '0.8',
      })
    );
    await client.syncTestSet('test-set-id');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/garak/sync/test-set-id');
    expect(opts.method).toBe('POST');
  });
});
