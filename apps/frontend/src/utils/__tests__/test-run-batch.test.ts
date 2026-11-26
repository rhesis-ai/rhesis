import {
  executeBatchedTestRuns,
  resolveSingleCreatedRun,
  watchRunHref,
  type BatchRunOutcome,
} from '../test-run-batch';
import type { TestRunsClient } from '@/utils/api-client/test-runs-client';

import type { TestRunBatchMember } from '@/utils/api-client/interfaces/test-run-batch';

const startedRun = (testRunId: string | null): TestRunBatchMember => ({
  test_set_id: 'ts-1',
  test_set_name: 'Safety',
  experiment_id: null,
  version: null,
  test_configuration_id: 'cfg-1',
  test_run_id: testRunId,
  test_run_name: null,
});

function outcomeWithMembers(
  results: TestRunBatchMember[],
  batchId = ''
): BatchRunOutcome {
  return {
    batch_id: batchId,
    members: results.map(result => ({
      test_set_id: result.test_set_id,
      experiment: null,
      result,
    })),
  };
}

describe('resolveSingleCreatedRun', () => {
  const clientReturning = (getTestRun: jest.Mock) =>
    ({ getTestRun }) as unknown as TestRunsClient;

  it('loads the one run the outcome started', async () => {
    const getTestRun = jest.fn().mockResolvedValue({ id: 'run-1' });

    const result = await resolveSingleCreatedRun(
      outcomeWithMembers([startedRun('run-1')]),
      clientReturning(getTestRun)
    );

    expect(result).toEqual({ id: 'run-1' });
    expect(getTestRun).toHaveBeenCalledWith('run-1');
  });

  it('returns null for a group of several runs', async () => {
    const getTestRun = jest.fn();

    const result = await resolveSingleCreatedRun(
      outcomeWithMembers([startedRun('run-1'), startedRun('run-2')], 'b-1'),
      clientReturning(getTestRun)
    );

    expect(result).toBeNull();
    expect(getTestRun).not.toHaveBeenCalled();
  });

  it('returns null when no run id came back', async () => {
    const getTestRun = jest.fn();

    expect(
      await resolveSingleCreatedRun(
        outcomeWithMembers([startedRun(null)]),
        clientReturning(getTestRun)
      )
    ).toBeNull();
    expect(
      await resolveSingleCreatedRun(
        outcomeWithMembers([]),
        clientReturning(getTestRun)
      )
    ).toBeNull();
    expect(getTestRun).not.toHaveBeenCalled();
  });

  it('returns null when the run cannot be loaded', async () => {
    const getTestRun = jest.fn().mockRejectedValue(new Error('404'));

    expect(
      await resolveSingleCreatedRun(
        outcomeWithMembers([startedRun('run-1')]),
        clientReturning(getTestRun)
      )
    ).toBeNull();
  });
});

describe('watchRunHref', () => {
  it('builds a test-run URL forcing Detail view', () => {
    expect(watchRunHref('run-123')).toBe('/test-runs/run-123?density=detail');
  });
});

describe('executeBatchedTestRuns', () => {
  const member = (overrides: object) => ({
    test_set_id: 'ts-1',
    test_set_name: 'Safety',
    experiment_id: null,
    version: null,
    test_configuration_id: 'cfg-1',
    test_run_id: 'run-1',
    test_run_name: 'witty-otter',
    ...overrides,
  });

  it('sends a tag and the shared settings in one request', async () => {
    const startBatch = jest.fn().mockResolvedValue({
      batch_id: 'b-1',
      test_set_tag: 'nightly',
      members: [
        member({ experiment_id: 'exp-1', version: 'v1' }),
        member({ test_set_id: 'ts-2', experiment_id: 'exp-1', version: 'v1' }),
      ],
    });
    const experiment = {
      experiment_id: 'exp-1',
      experiment_name: 'Tuning',
      version: 'v1',
    };

    const outcome = await executeBatchedTestRuns({
      testRunsClient: { startBatch } as unknown as TestRunsClient,
      testSetTag: 'nightly',
      endpointId: 'ep-1',
      selectedExperiments: [experiment],
      baseAttributes: {
        execution_mode: 'Parallel',
        run_preflight_checks: true,
        metrics: [{ id: 'm-1', name: 'Accuracy' }],
        tests_tagged: ['smoke'],
      },
    });

    expect(startBatch).toHaveBeenCalledWith({
      test_set_tag: 'nightly',
      endpoint_id: 'ep-1',
      experiments: [{ experiment_id: 'exp-1', version: 'v1' }],
      run_settings: {
        execution_options: {
          execution_mode: 'Parallel',
          run_preflight_checks: true,
        },
        metrics: [{ id: 'm-1', name: 'Accuracy' }],
        tests_tagged: ['smoke'],
      },
    });
    expect(outcome.batch_id).toBe('b-1');
    expect(outcome.members.map(m => [m.test_set_id, m.experiment])).toEqual([
      ['ts-1', experiment],
      ['ts-2', experiment],
    ]);
  });

  it('reports a single run with an empty batch id', async () => {
    const startBatch = jest.fn().mockResolvedValue({
      batch_id: null,
      test_set_tag: null,
      members: [member({})],
    });

    const outcome = await executeBatchedTestRuns({
      testRunsClient: { startBatch } as unknown as TestRunsClient,
      testSetIds: ['ts-1'],
      endpointId: 'ep-1',
      selectedExperiments: [],
      baseAttributes: { reference_test_run_id: 'run-0' },
    });

    expect(startBatch.mock.calls[0][0]).toMatchObject({
      test_set_ids: ['ts-1'],
      run_settings: { reference_test_run_id: 'run-0' },
    });
    expect(outcome).toMatchObject({
      batch_id: '',
      members: [{ experiment: null }],
    });
  });
});
