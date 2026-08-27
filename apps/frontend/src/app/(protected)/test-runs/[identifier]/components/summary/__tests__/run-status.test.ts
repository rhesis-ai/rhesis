import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
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

describe('deriveRunStatus', () => {
  it('calculates duration from timestamps', () => {
    const result = deriveRunStatus(makeTestRun());
    // 5 minutes 30 seconds = 330000ms
    expect(result.duration).toBe(330000);
  });

  it('returns null duration when the run has not completed', () => {
    const result = deriveRunStatus(makeTestRun({ attributes: {} }));
    expect(result.duration).toBeNull();
  });

  it('returns null duration when only started_at is present', () => {
    const result = deriveRunStatus(
      makeTestRun({ attributes: { started_at: '2026-01-01T00:00:00Z' } })
    );
    expect(result.duration).toBeNull();
  });
});
