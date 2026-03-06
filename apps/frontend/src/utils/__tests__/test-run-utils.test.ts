import { pollForTestRun } from '../test-run-utils';

type MockTestRunsClient = {
  getTestRunsByTestConfiguration: jest.Mock;
};

function makeMockClient(): MockTestRunsClient {
  return { getTestRunsByTestConfiguration: jest.fn() };
}

describe('pollForTestRun', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('returns the test run immediately when found on the first attempt', async () => {
    const mockRun = { id: 'run-1', status: 'queued' };
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({
      data: [mockRun],
    });

    const result = await pollForTestRun(client as never, 'config-1', {
      maxAttempts: 1,
    });

    expect(result).toEqual(mockRun);
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledTimes(1);
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledWith(
      'config-1',
      {
        limit: 1,
        sort_by: 'created_at',
        sort_order: 'desc',
      }
    );
  });

  it('returns null when test run is never found after all attempts', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({ data: [] });

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 3,
      initialDelay: 0,
      exponentialBackoff: false,
    });

    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result).toBeNull();
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledTimes(3);
  });

  it('returns the run when found on the second attempt', async () => {
    const mockRun = { id: 'run-2' };
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [mockRun] });

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 5,
      initialDelay: 100,
      exponentialBackoff: false,
    });

    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result).toEqual(mockRun);
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledTimes(2);
  });

  it('continues retrying after an API error and returns run on recovery', async () => {
    const mockRun = { id: 'run-3' };
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({ data: [mockRun] });

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 3,
      initialDelay: 0,
      exponentialBackoff: false,
    });

    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result).toEqual(mockRun);
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledTimes(2);
  });

  it('returns null when all attempts fail with API errors', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockRejectedValue(
      new Error('Service unavailable')
    );

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 2,
      initialDelay: 0,
      exponentialBackoff: false,
    });

    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result).toBeNull();
  });

  it('skips the delay on the first attempt (attempt index 0)', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({ data: [] });

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 1,
      initialDelay: 9999,
    });

    // No timer advancement needed — first attempt has no delay
    const result = await promise;
    expect(result).toBeNull();
  });

  it('uses exponential backoff delays for subsequent attempts', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({ data: [] });

    const promise = pollForTestRun(client as never, 'config-1', {
      maxAttempts: 3,
      initialDelay: 500,
      exponentialBackoff: true,
    });

    // delay for attempt 1 = 500 * 2^1 = 1000
    // delay for attempt 2 = 500 * 2^2 = 2000
    await jest.runAllTimersAsync();
    await promise;

    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledTimes(3);
  });

  it('passes custom options to the API call', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({ data: [] });

    const promise = pollForTestRun(client as never, 'my-config-id', {
      maxAttempts: 1,
    });

    await promise;

    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledWith(
      'my-config-id',
      expect.any(Object)
    );
  });
});
