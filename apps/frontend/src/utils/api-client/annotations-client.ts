import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Annotation,
  AnnotationCreate,
  AnnotationsQueryParams,
  AnnotationUpdate,
} from './interfaces/annotation';
import { PaginatedResponse } from './interfaces/pagination';

export class AnnotationsClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getAnnotations(
    params: AnnotationsQueryParams = {}
  ): Promise<PaginatedResponse<Annotation>> {
    const { skip = 0, limit = 50, sort_by, sort_order, ...filters } = params;
    return this.fetchPaginated<Annotation>(API_ENDPOINTS.annotations, {
      skip,
      limit,
      ...(sort_by ? { sort_by } : {}),
      ...(sort_order ? { sort_order } : {}),
      // Undefined entries are dropped by fetchPaginated, but `resolved: false`
      // is meaningful and must survive.
      ...Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value !== undefined)
      ),
    });
  }

  /** Every annotation on one parent, oldest request wins the whole list. */
  async getByEntity(
    entityType: string,
    entityId: string
  ): Promise<Annotation[]> {
    return this.fetch<Annotation[]>(
      `${API_ENDPOINTS.annotations}/entity/${entityType}/${entityId}?skip=0&limit=100`
    );
  }

  async createAnnotation(data: AnnotationCreate): Promise<Annotation> {
    return this.fetch<Annotation>(`${API_ENDPOINTS.annotations}/`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAnnotation(
    annotationId: string,
    data: AnnotationUpdate
  ): Promise<Annotation> {
    return this.fetch<Annotation>(
      `${API_ENDPOINTS.annotations}/${annotationId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    );
  }

  async deleteAnnotation(annotationId: string): Promise<Annotation> {
    return this.fetch<Annotation>(
      `${API_ENDPOINTS.annotations}/${annotationId}`,
      { method: 'DELETE' }
    );
  }
}
