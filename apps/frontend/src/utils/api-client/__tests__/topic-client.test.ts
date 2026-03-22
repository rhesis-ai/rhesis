import { TopicClient } from '../topic-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const TOPIC_ID = 't1t1t1t1-0000-0000-0000-000000000001' as UUID;

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

describe('TopicClient', () => {
  let client: TopicClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TopicClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches topics with default params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'top-1' }]));
    const result = await client.getTopics();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/topics`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes entity_type and $filter when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getTopics({
      entity_type: 'Test',
      $filter: "name eq 'Privacy'",
    });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('entity_type=Test');
    expect(calledUrl).toContain('%24filter');
  });

  it('fetches a single topic by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: TOPIC_ID }));
    await client.getTopic(TOPIC_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/topics/${TOPIC_ID}`),
      expect.any(Object)
    );
  });

  it('creates a topic with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-top' }));
    await client.createTopic({ name: 'Privacy' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics');
    expect(opts.method).toBe('POST');
  });

  it('findTopicByName returns topic if found', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'top-1', name: 'Privacy' }]));
    const result = await client.findTopicByName('Privacy');
    expect(result).toMatchObject({ id: 'top-1', name: 'Privacy' });
  });

  it('findTopicByName returns null if not found', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    const result = await client.findTopicByName('Nonexistent');
    expect(result).toBeNull();
  });

  it('getOrCreateTopic creates a new topic when not found', async () => {
    fetchMock
      .mockResolvedValueOnce(makeFetch([]))
      .mockResolvedValueOnce(makeFetch({ id: 'new-top', name: 'Privacy' }));

    const result = await client.getOrCreateTopic('Privacy');

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result).toMatchObject({ name: 'Privacy' });
    expect(fetchMock.mock.calls[1][1].method).toBe('POST');
  });
});
