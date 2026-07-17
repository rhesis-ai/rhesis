import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  AnnotationListItem,
  AnnotationsQueryParams,
} from './interfaces/annotation';

export class AnnotationsClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getAnnotations(
    params: AnnotationsQueryParams = {}
  ): Promise<{ data: AnnotationListItem[]; totalCount: number }> {
    const queryParams = new URLSearchParams();

    if (params.skip !== undefined) {
      queryParams.append('skip', params.skip.toString());
    }
    if (params.limit !== undefined) {
      queryParams.append('limit', params.limit.toString());
    }
    if (params.source) {
      queryParams.append('source', params.source);
    }
    if (params.search) {
      queryParams.append('search', params.search);
    }
    if (params.resolved !== undefined) {
      queryParams.append('resolved', params.resolved.toString());
    }
    if (params.rating) {
      queryParams.append('rating', params.rating);
    }
    if (params.target_type) {
      queryParams.append('target_type', params.target_type);
    }

    const path = `${API_ENDPOINTS.annotations}/?${queryParams.toString()}`;
    const url = this.baseUrl + path;
    const headers = this.getHeaders();

    const response = await fetch(url, {
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} - ${response.statusText}`);
    }

    const data = (await response.json()) as AnnotationListItem[];
    const totalCount = parseInt(response.headers.get('X-Total-Count') || '0');

    return { data, totalCount };
  }
}
