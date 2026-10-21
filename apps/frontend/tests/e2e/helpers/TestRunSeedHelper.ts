import { type Page, expect } from '@playwright/test';

/**
 * Seeds a finished test run with results through the backend proxy.
 *
 * The E2E stack has no Celery worker and a deliberately dead model URL, so a
 * run started from the UI stays Queued and never gets results. Pages that need
 * results (run detail, annotations) seed one here instead. CI shards each start
 * from a fresh database, so specs can't rely on another file having made a run.
 */

interface Named {
  id: string;
  name?: string;
}

/** The browser client sends the active project as a header; do the same. */
async function projectHeaders(page: Page) {
  const cookie = (await page.context().cookies()).find(
    c => c.name === 'rh_active_project_id'
  );
  expect(cookie, 'active project cookie').toBeTruthy();
  return { 'X-Project-Id': cookie?.value ?? '' };
}

async function getJson<T>(page: Page, path: string): Promise<T> {
  const res = await page.request.get(`/api/backend${path}`, {
    headers: await projectHeaders(page),
  });
  expect(res.ok(), `GET ${path} -> ${res.status()}`).toBeTruthy();
  return (await res.json()) as T;
}

async function postJson<T>(page: Page, path: string, data: object): Promise<T> {
  const res = await page.request.post(`/api/backend${path}`, {
    data,
    headers: await projectHeaders(page),
  });
  expect(res.ok(), `POST ${path} -> ${res.status()}`).toBeTruthy();
  return (await res.json()) as T;
}

async function statusId(page: Page, name: string, entityType: string) {
  const statuses = await getJson<Named[]>(
    page,
    `/statuses/?entity_type=${entityType}&limit=100`
  );
  const status = statuses.find(s => s.name === name);
  expect(status, `status ${entityType}/${name}`).toBeTruthy();
  return status?.id;
}

function metricResult(passed: boolean) {
  return {
    score: passed ? 0.9 : 0.2,
    threshold: 0.5,
    is_successful: passed,
    reason: passed ? 'The answer is accurate.' : 'The answer is off-topic.',
    backend: 'rhesis',
    description: 'Seeded by E2E',
  };
}

/**
 * Creates a Completed run on the seeded test set and endpoint: the first test
 * passes, the second fails. Returns the run's name so tests can find its row.
 * Call after a page load, which sets the active project cookie.
 */
export async function seedCompletedTestRun(page: Page): Promise<string> {
  const [testSet] = await getJson<Named[]>(page, '/test_sets/?limit=1');
  const [endpoint] = await getJson<Named[]>(page, '/endpoints/?limit=1');
  expect(testSet && endpoint, 'Quick Start test set and endpoint').toBeTruthy();
  const tests = await getJson<Named[]>(
    page,
    `/test_sets/${testSet.id}/tests?limit=2`
  );
  expect(tests.length, 'tests in the seeded test set').toBe(2);

  const config = await postJson<Named>(page, '/test_configurations/', {
    endpoint_id: endpoint.id,
    test_set_id: testSet.id,
  });

  const now = new Date().toISOString();
  const name = `e2e-seeded-run-${Date.now()}`;
  const run = await postJson<Named>(page, '/test_runs/', {
    name,
    test_configuration_id: config.id,
    status_id: await statusId(page, 'Completed', 'TestRun'),
    attributes: { started_at: now, completed_at: now, total_tests: 2 },
  });

  const outcomes = [true, false];
  for (const [i, t] of tests.entries()) {
    const passed = outcomes[i];
    await postJson(page, '/test_results/', {
      test_configuration_id: config.id,
      test_run_id: run.id,
      test_id: t.id,
      status_id: await statusId(page, passed ? 'Pass' : 'Fail', 'TestResult'),
      execution: 'ok',
      verdict: passed ? 'pass' : 'fail',
      test_metrics: {
        execution_time: 1.2,
        metrics: { 'Answer Fluency': metricResult(passed) },
      },
      test_output: { output: 'Seeded response from the E2E helper.' },
    });
  }

  return name;
}
