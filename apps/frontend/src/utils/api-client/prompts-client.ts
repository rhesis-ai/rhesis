import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Prompt, PromptCreate, PromptUpdate } from './interfaces/prompt';

export class PromptsClient extends BaseApiClient {
  /**
   * Get a list of prompts with optional filtering and pagination
   * @param options.filter - OData filter expression for filtering prompts
   */
  async getPrompts(options: {
    skip?: number;
    limit?: number;
    sortBy?: string;
    sortOrder?: string;
    topic_id?: string;
    behavior_id?: string;
    category_id?: string;
    filter?: string;
  } = {}): Promise<Prompt[]> {
    const queryParams = new URLSearchParams();
    if (options.skip !== undefined) queryParams.append('skip', options.skip.toString());
    if (options.limit !== undefined) queryParams.append('limit', options.limit.toString());
    if (options.sortBy) queryParams.append('sort_by', options.sortBy);
    if (options.sortOrder) queryParams.append('sort_order', options.sortOrder);
    if (options.topic_id) queryParams.append('topic_id', options.topic_id);
    if (options.behavior_id) queryParams.append('behavior_id', options.behavior_id);
    if (options.category_id) queryParams.append('category_id', options.category_id);
    if (options.filter) queryParams.append('$filter', options.filter);

    const queryString = queryParams.toString();
    const url = queryString ? `${API_ENDPOINTS.prompts}?${queryString}` : API_ENDPOINTS.prompts;

    return this.fetch<Prompt[]>(url, {
      cache: 'no-store'
    });
  }

  /**
   * Get a single prompt by ID
   * @param id - The prompt ID to retrieve
   * @returns The prompt details
   */
  async getPrompt(id: string): Promise<Prompt> {
    // Using the prompts endpoint with ID parameter
    return this.fetch<Prompt>(`${API_ENDPOINTS.prompts}/${id}`);
  }

  /**
   * Create a new prompt
   */
  async createPrompt(prompt: PromptCreate): Promise<Prompt> {
    return this.fetch<Prompt>(API_ENDPOINTS.prompts, {
      method: 'POST',
      body: JSON.stringify(prompt),
    });
  }

  /**
   * Update an existing prompt
   */
  async updatePrompt(id: string, prompt: PromptUpdate): Promise<Prompt> {
    return this.fetch<Prompt>(`${API_ENDPOINTS.prompts}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(prompt),
    });
  }

  /**
   * Delete a prompt
   */
  async deletePrompt(id: string): Promise<Prompt> {
    return this.fetch<Prompt>(`${API_ENDPOINTS.prompts}/${id}`, {
      method: 'DELETE',
    });
  }
} 