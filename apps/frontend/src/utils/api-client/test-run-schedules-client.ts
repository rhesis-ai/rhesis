import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import type {
  OccurrenceEdit,
  ScheduleListParams,
  ScheduleOccurrences,
  SchedulePreview,
  ScheduleScope,
  ScheduleSpec,
  TestRunSchedule,
  TestRunScheduleCreate,
  TestRunScheduleDetail,
  TestRunScheduleUpdate,
} from './interfaces/test-run-schedule';

const base = API_ENDPOINTS.testRunSchedules;

const withQuery = (
  path: string,
  params: Record<string, string | string[] | undefined>
) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) value.forEach(v => query.append(key, v));
    else if (value !== undefined) query.append(key, value);
  });
  const text = query.toString();
  return text ? `${path}?${text}` : path;
};

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export class TestRunSchedulesClient extends BaseApiClient {
  async list(params: ScheduleListParams = {}): Promise<TestRunSchedule[]> {
    return this.fetch<TestRunSchedule[]>(
      withQuery(`${base}/`, {
        test_set_id: params.test_set_id,
        status: params.status,
      }),
      { cache: 'no-store' }
    );
  }

  async get(
    id: string,
    runsLimit = 10,
    runsOffset = 0
  ): Promise<TestRunScheduleDetail> {
    return this.fetch<TestRunScheduleDetail>(
      withQuery(`${base}/${id}`, {
        runs_limit: String(runsLimit),
        runs_offset: String(runsOffset),
      }),
      { cache: 'no-store' }
    );
  }

  async create(body: TestRunScheduleCreate): Promise<TestRunSchedule[]> {
    return this.fetch<TestRunSchedule[]>(`${base}/`, json('POST', body));
  }

  async preview(spec: Partial<ScheduleSpec>): Promise<SchedulePreview> {
    return this.fetch<SchedulePreview>(`${base}/preview`, json('POST', spec));
  }

  async occurrences(from: Date, to: Date): Promise<ScheduleOccurrences> {
    return this.fetch<ScheduleOccurrences>(
      withQuery(`${base}/occurrences`, {
        from: from.toISOString(),
        to: to.toISOString(),
      }),
      { cache: 'no-store' }
    );
  }

  async update(
    id: string,
    body: TestRunScheduleUpdate
  ): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}`, json('PATCH', body));
  }

  async remove(id: string): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}`, json('DELETE'));
  }

  async runNow(id: string): Promise<{ test_run_id: string; task_id: string }> {
    return this.fetch(`${base}/${id}/run_now`, json('POST'));
  }

  async skipNext(id: string): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}/skip_next`, json('POST'));
  }

  async pause(id: string): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}/pause`, json('POST'));
  }

  async resume(id: string): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}/resume`, json('POST'));
  }

  async takeOver(id: string): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(`${base}/${id}/take_over`, json('POST'));
  }

  async editOccurrence(
    id: string,
    occurrence: string,
    scope: ScheduleScope,
    body: OccurrenceEdit
  ): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(
      withQuery(`${base}/${id}/occurrences/${encodeURIComponent(occurrence)}`, {
        scope,
      }),
      json('PATCH', body)
    );
  }

  async deleteOccurrence(
    id: string,
    occurrence: string,
    scope: ScheduleScope
  ): Promise<TestRunSchedule> {
    return this.fetch<TestRunSchedule>(
      withQuery(`${base}/${id}/occurrences/${encodeURIComponent(occurrence)}`, {
        scope,
      }),
      json('DELETE')
    );
  }
}
