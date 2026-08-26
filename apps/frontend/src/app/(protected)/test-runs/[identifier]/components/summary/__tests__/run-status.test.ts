import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

jest.mock('@/utils/test-result-status', () => ({
  getEffectiveTestResultStatus: jest.fn((result: { _mockStatus?: string }) => {
    return result._mockStatus ?? 'Pass';
  }),
}));

import { deriveRunStatus } from '../run-status';

function makeTestRun(overrides: Partial<TestRunDetail> = {}): TestRunDetail {
  return {
    id: 'tr-1',
    name: 'Test Run 1',
    status: { name: 'Completed' },
    attributes: {
      started_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:05:30Z',
    },
    ...overrides,
  } as TestRunDetail;
}

function makeResult(status: string): TestResultDetail {
  return { _mockStatus: status } as unknown as TestResultDetail;
}

describe('deriveRunStatus', () => {
  it('maps Completed backend status', () => {
    const result = deriveRunStatus(makeTestRun());
    expect(result.status).toBe('completed');
  });

  it('maps Queued backend status with null duration', () => {
    const result = deriveRunStatus(
      makeTestRun({
        status: { name: 'Queued' } as TestRunDetail['status'],
        attributes: {},
      })
    );
    expect(result.status).toBe('queued');
    expect(result.duration).toBeNull();
  });

  it('maps Progress backend status', () => {
    const result = deriveRunStatus(
      makeTestRun({
        status: { name: 'Progress' } as TestRunDetail['status'],
      })
    );
    expect(result.status).toBe('progress');
  });

  it('maps all six backend statuses', () => {
    const statuses = [
      'Queued',
      'Progress',
      'Completed',
      'Partial',
      'Failed',
      'Cancelled',
    ] as const;
    const expected = [
      'queued',
      'progress',
      'completed',
      'partial',
      'failed',
      'cancelled',
    ];
    for (let i = 0; i < statuses.length; i++) {
      const result = deriveRunStatus(
        makeTestRun({
          status: { name: statuses[i] } as TestRunDetail['status'],
        })
      );
      expect(result.status).toBe(expected[i]);
    }
  });

  it('returns null passRate with no test results', () => {
    const result = deriveRunStatus(makeTestRun(), []);
    expect(result.passRate).toBeNull();
    expect(result.total).toBe(0);
  });

  it('calculates pass rate correctly', () => {
    const results = [
      makeResult('Pass'),
      makeResult('Pass'),
      makeResult('Pass'),
      makeResult('Fail'),
    ];
    const result = deriveRunStatus(makeTestRun(), results);
    expect(result.passRate).toBe(0.75);
    expect(result.passed).toBe(3);
    expect(result.failed).toBe(1);
  });

  it('calculates duration from timestamps', () => {
    const result = deriveRunStatus(makeTestRun());
    // 5 minutes 30 seconds = 330000ms
    expect(result.duration).toBe(330000);
  });

  it('infers progress when started but not completed', () => {
    const result = deriveRunStatus(
      makeTestRun({
        status: { name: 'Unknown' } as TestRunDetail['status'],
        attributes: {
          started_at: '2026-01-01T00:00:00Z',
        },
      })
    );
    expect(result.status).toBe('progress');
  });
});
