import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  AnnotationListItem,
  AnnotationsQueryParams,
} from './interfaces/annotation';
import { PaginatedResponse } from './interfaces/pagination';

export class AnnotationsClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getAnnotations(
    params: AnnotationsQueryParams = {}
  ): Promise<PaginatedResponse<AnnotationListItem>> {
    return this.fetchPaginated<AnnotationListItem>(API_ENDPOINTS.annotations, {
      skip: params.skip ?? 0,
      limit: params.limit ?? 50,
      ...(params.source ? { source: params.source } : {}),
      ...(params.search ? { search: params.search } : {}),
      ...(params.resolved !== undefined ? { resolved: params.resolved } : {}),
      ...(params.rating ? { rating: params.rating } : {}),
      ...(params.target_type ? { target_type: params.target_type } : {}),
    });
  }
}
