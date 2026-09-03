import {
  resolveSingleCreatedRun,
  watchRunHref,
  type BatchRunOutcome,
} from '../test-run-batch';

type MockTestRunsClient = {
  getTestRunsByTestConfiguration: jest.Mock;
};

function makeMockClient(): MockTestRunsClient {
  return { getTestRunsByTestConfiguration: jest.fn() };
}

function outcomeWithMembers(results: unknown[], batchId = ''): BatchRunOutcome {
  return {
    batch_id: batchId,
    members: results.map(result => ({
      test_set_id: 'ts-1',
      experiment: null,
      result,
    })),
  };
}

describe('resolveSingleCreatedRun', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('polls for and returns the run when exactly one member was created', async () => {
    const mockRun = { id: 'run-1' };
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({
      data: [mockRun],
    });

    const outcome = outcomeWithMembers([
      { id: 'ts-1', test_configuration_id: 'config-1' },
    ]);

    const result = await resolveSingleCreatedRun(outcome, client as never);

    expect(result).toEqual(mockRun);
    expect(client.getTestRunsByTestConfiguration).toHaveBeenCalledWith(
      'config-1',
      expect.any(Object)
    );
  });

  it('returns null for a batch outcome with more than one member', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({
      data: [{ id: 'run-1' }],
    });

    const outcome = outcomeWithMembers(
      [
        { id: 'ts-1', test_configuration_id: 'config-1' },
        { id: 'ts-2', test_configuration_id: 'config-2' },
      ],
      'batch-1'
    );

    const result = await resolveSingleCreatedRun(outcome, client as never);

    expect(result).toBeNull();
    expect(client.getTestRunsByTestConfiguration).not.toHaveBeenCalled();
  });

  it('returns null for an empty outcome (no test sets resolved)', async () => {
    const client = makeMockClient();
    const outcome = outcomeWithMembers([]);

    const result = await resolveSingleCreatedRun(outcome, client as never);

    expect(result).toBeNull();
    expect(client.getTestRunsByTestConfiguration).not.toHaveBeenCalled();
  });

  it('returns null when the single member has no test_configuration_id', async () => {
    const client = makeMockClient();
    const outcome = outcomeWithMembers([{ id: 'ts-1' }]);

    const result = await resolveSingleCreatedRun(outcome, client as never);

    expect(result).toBeNull();
    expect(client.getTestRunsByTestConfiguration).not.toHaveBeenCalled();
  });

  it('returns null when polling times out before the run shows up', async () => {
    const client = makeMockClient();
    client.getTestRunsByTestConfiguration.mockResolvedValue({ data: [] });

    const outcome = outcomeWithMembers([
      { id: 'ts-1', test_configuration_id: 'config-1' },
    ]);

    const promise = resolveSingleCreatedRun(outcome, client as never);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result).toBeNull();
  });
});

describe('watchRunHref', () => {
  it('builds a test-run URL forcing Detail view', () => {
    expect(watchRunHref('run-123')).toBe('/test-runs/run-123?density=detail');
  });
});
