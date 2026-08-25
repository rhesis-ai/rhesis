import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Job, JobActivity, JobsQueryParams } from './interfaces/job';

export class JobsClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getJobs(
    params: JobsQueryParams = {}
  ): Promise<{ data: Job[]; totalCount: number }> {
    const { data, pagination } = await this.fetchPaginated<Job>('jobs', {
      skip: params.skip ?? 0,
      limit: params.limit ?? 50,
      sort_by: params.sort_by,
      sort_order: params.sort_order,
      $filter: params.$filter,
    });

    return { data, totalCount: pagination.totalCount };
  }

  /**
   * Detail routes sit under `/jobs/detail/` because the deprecated
   * `GET /jobs/{celery_task_id}` alias still owns the bare path.
   */
  async getJob(jobId: string): Promise<Job> {
    return this.fetch<Job>(`${API_ENDPOINTS.jobs}/detail/${jobId}`);
  }

  async getJobActivity(
    jobId: string,
    options: { afterSequence?: number; limit?: number } = {}
  ): Promise<JobActivity> {
    const queryParams = new URLSearchParams();
    if (options.afterSequence !== undefined)
      queryParams.append('after_sequence', options.afterSequence.toString());
    if (options.limit !== undefined)
      queryParams.append('limit', options.limit.toString());

    const query = queryParams.toString();
    const path = `${API_ENDPOINTS.jobs}/detail/${jobId}/activity${
      query ? `?${query}` : ''
    }`;
    return this.fetch<JobActivity>(path);
  }

  /**
   * Ask a job to stop. Returns it in `cancelling`, not `cancelled`: a running
   * job only stops once it notices the request, so the response would be lying
   * if it claimed otherwise.
   */
  async cancelJob(jobId: string): Promise<Job> {
    return this.fetch<Job>(`${API_ENDPOINTS.jobs}/detail/${jobId}/cancel`, {
      method: 'POST',
    });
  }
}
