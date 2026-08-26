import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  MetricTuningCase,
  MetricTuningCaseCreate,
  MetricTuningCaseDeleteResponse,
  MetricTuningCaseUpdate,
  MetricTuningImprovement,
  MetricTuningReviewCreate,
  MetricTuningRun,
} from './interfaces/metric-tuning';
import { UUID } from 'crypto';

/**
 * Client for the experimental metric tuning endpoints.
 *
 * Kept separate from `MetricsClient` so the feature can be removed by deleting
 * this file, its interfaces file, and one factory getter.
 */
export class MetricTuningClient extends BaseApiClient {
  private basePath(metricId: UUID | string): string {
    return `${API_ENDPOINTS.metrics}/${metricId}/tuning/cases`;
  }

  private runPath(metricId: UUID | string): string {
    return `${API_ENDPOINTS.metrics}/${metricId}/tuning/run`;
  }

  private reviewsPath(metricId: UUID | string): string {
    return `${API_ENDPOINTS.metrics}/${metricId}/tuning/reviews`;
  }

  private improvePath(metricId: UUID | string): string {
    return `${API_ENDPOINTS.metrics}/${metricId}/tuning/improve`;
  }

  /** Cases for a metric. Empty when it has no tuning test set yet. */
  async getTuningCases(metricId: UUID | string): Promise<MetricTuningCase[]> {
    return this.fetch<MetricTuningCase[]>(this.basePath(metricId), {
      cache: 'no-store',
    });
  }

  /** Adds a case, creating the metric's tuning test set on the first call. */
  async createTuningCase(
    metricId: UUID | string,
    data: MetricTuningCaseCreate
  ): Promise<MetricTuningCase> {
    return this.fetch<MetricTuningCase>(this.basePath(metricId), {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTuningCase(
    metricId: UUID | string,
    caseId: UUID | string,
    data: MetricTuningCaseUpdate
  ): Promise<MetricTuningCase> {
    return this.fetch<MetricTuningCase>(
      `${this.basePath(metricId)}/${caseId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    );
  }

  async deleteTuningCase(
    metricId: UUID | string,
    caseId: UUID | string
  ): Promise<MetricTuningCaseDeleteResponse> {
    return this.fetch<MetricTuningCaseDeleteResponse>(
      `${this.basePath(metricId)}/${caseId}`,
      { method: 'DELETE' }
    );
  }

  /**
   * Records what a reviewer made of the metric's verdict for one case.
   *
   * A rejection needs a comment — the API refuses a blank one, so the caller
   * must collect it first.
   */
  async reviewTuningCase(
    metricId: UUID | string,
    caseId: UUID | string,
    data: MetricTuningReviewCreate
  ): Promise<MetricTuningCase> {
    return this.fetch<MetricTuningCase>(
      `${this.basePath(metricId)}/${caseId}/review`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  /**
   * Accepts every case that is still unreviewed and has a verdict, and returns
   * the whole case list as it now stands.
   */
  async acceptRemainingTuningCases(
    metricId: UUID | string
  ): Promise<MetricTuningCase[]> {
    return this.fetch<MetricTuningCase[]>(
      `${this.reviewsPath(metricId)}/accept-rest`,
      { method: 'POST' }
    );
  }

  /** The metric's latest run. `never_run` when there has not been one. */
  async getTuningRun(metricId: UUID | string): Promise<MetricTuningRun> {
    return this.fetch<MetricTuningRun>(this.runPath(metricId), {
      cache: 'no-store',
    });
  }

  /**
   * Starts a run over the metric's cases and returns the in-progress summary.
   *
   * The work happens in the background — poll `getTuningRun` for progress.
   * Every run is one LLM call per case, so this is only ever called from an
   * explicit action, never from an effect that watches the cases.
   */
  async startTuningRun(metricId: UUID | string): Promise<MetricTuningRun> {
    return this.fetch<MetricTuningRun>(this.runPath(metricId), {
      method: 'POST',
    });
  }

  /**
   * Proposes a rewrite of the metric from the rejections its reviewers wrote.
   *
   * Saves nothing — applying is an ordinary `updateMetric` with the fields this
   * returned. Synchronous and one LLM call, so it is only ever called from an
   * explicit action. Refused when no rejection currently stands.
   */
  async improveFromReviews(
    metricId: UUID | string
  ): Promise<MetricTuningImprovement> {
    return this.fetch<MetricTuningImprovement>(this.improvePath(metricId), {
      method: 'POST',
    });
  }
}
