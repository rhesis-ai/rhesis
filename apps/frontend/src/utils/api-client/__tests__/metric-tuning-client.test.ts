import { MetricTuningClient } from '../metric-tuning-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://localhost/api/backend';
const METRIC_ID = 'm1m1m1m1-0000-0000-0000-000000000001' as UUID;
const TEST_ID = 't1t1t1t1-0000-0000-0000-000000000001' as UUID;

function makeFetch(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: () => null,
      entries: () => [],
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

describe('MetricTuningClient', () => {
  let client: MetricTuningClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new MetricTuningClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('lists tuning cases for a metric', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: TEST_ID, input: 'hi' }]));

    const result = await client.getTuningCases(METRIC_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/metrics/${METRIC_ID}/tuning/cases`,
      expect.objectContaining({ cache: 'no-store' })
    );
    expect(result).toHaveLength(1);
  });

  it('creates a tuning case', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: TEST_ID }));

    await client.createTuningCase(METRIC_ID, {
      input: 'How are you?',
      output: 'Fine.',
      expected: 'pass',
      rationale: 'not toxic',
    });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/metrics/${METRIC_ID}/tuning/cases`);
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      input: 'How are you?',
      output: 'Fine.',
      expected: 'pass',
      rationale: 'not toxic',
    });
  });

  it('sends only the fields given on update', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: TEST_ID }));

    await client.updateTuningCase(METRIC_ID, TEST_ID, { expected: 'fail' });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(
      `${BASE_URL}/metrics/${METRIC_ID}/tuning/cases/${TEST_ID}`
    );
    expect(options.method).toBe('PUT');
    expect(JSON.parse(options.body)).toEqual({ expected: 'fail' });
  });

  it('deletes a tuning case', async () => {
    fetchMock.mockResolvedValue(makeFetch({ deleted: true, case_id: TEST_ID }));

    const result = await client.deleteTuningCase(METRIC_ID, TEST_ID);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(
      `${BASE_URL}/metrics/${METRIC_ID}/tuning/cases/${TEST_ID}`
    );
    expect(options.method).toBe('DELETE');
    expect(result.deleted).toBe(true);
  });
});
