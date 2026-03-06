import { TasksClient } from '../tasks-client';

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

describe('TasksClient', () => {
  let client: TasksClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TasksClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches tasks and returns data with totalCount from x-total-count header', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'task-1' }], 200, { 'x-total-count': '5' })
    );
    const result = await client.getTasks();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/tasks`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
    expect(result.totalCount).toBe(5);
  });

  it('includes $filter in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '0' }));
    await client.getTasks({ $filter: "status eq 'open'" });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('%24filter');
  });

  it('fetches a single task by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'task-1' }));
    await client.getTask('task-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-1'),
      expect.any(Object)
    );
  });

  it('creates a task with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-task' }));
    const payload = { title: 'Fix bug' };
    await client.createTask(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tasks');
    expect(opts.method).toBe('POST');
  });

  it('updates a task with PATCH', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'task-1' }));
    await client.updateTask('task-1', { title: 'Updated' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tasks/task-1');
    expect(opts.method).toBe('PATCH');
  });

  it('gets tasks by entity and returns totalCount from header', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'task-1' }], 200, { 'x-total-count': '1' })
    );
    const result = await client.getTasksByEntity('test_run', 'run-id-1');
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/tasks/test_run/run-id-1');
    expect(result.totalCount).toBe(1);
  });
});
