import { BaseApiClient } from './base-client';

/** Which OWASP Top 10 report to generate attacks from */
export type OwaspFramework = 'llm' | 'agentic';

/**
 * A single risk category (report section) within an OWASP Top 10 report
 */
export interface OwaspCategory {
  id: string;
  name: string;
}

/**
 * Response for listing the risk categories of an OWASP report
 */
export interface OwaspCategoriesResponse {
  framework: OwaspFramework;
  report_url: string;
  categories: OwaspCategory[];
}

/**
 * Request to generate a test set from an OWASP Top 10 report
 */
export interface OwaspGenerateRequest {
  framework: OwaspFramework;
  purpose: string;
  categories?: string[];
  num_tests?: number;
  name?: string;
  batch_size?: number;
  model_id?: string;
}

/**
 * Response from an OWASP generation request (async task)
 */
export interface OwaspGenerateResponse {
  task_id: string;
  framework: OwaspFramework;
  num_tests: number;
  message: string;
}

/**
 * Client for OWASP Top 10 test set generation API endpoints
 */
export class OwaspClient extends BaseApiClient {
  /**
   * List the risk categories for an OWASP Top 10 report
   */
  async listCategories(
    framework: OwaspFramework = 'llm'
  ): Promise<OwaspCategoriesResponse> {
    return this.fetch<OwaspCategoriesResponse>(
      `/owasp/categories?framework=${framework}`
    );
  }

  /**
   * Generate a test set of adversarial prompts from an OWASP Top 10 report
   */
  async generateTestSet(
    request: OwaspGenerateRequest
  ): Promise<OwaspGenerateResponse> {
    return this.fetch<OwaspGenerateResponse>('/owasp/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}
