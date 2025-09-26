import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Topic,
  TopicCreate,
  TopicUpdate,
  TopicsQueryParams,
} from './interfaces/topic';
import { UUID } from 'crypto';

export class TopicClient extends BaseApiClient {
  async getTopics(params: TopicsQueryParams = {}): Promise<Topic[]> {
    const {
      skip = 0,
      limit = 100,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
      entity_type,
    } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      queryParams.append('$filter', $filter);
    }
    if (entity_type) {
      queryParams.append('entity_type', entity_type);
    }

    const url = `${API_ENDPOINTS.topics}?${queryParams.toString()}`;

    return this.fetch<Topic[]>(url, {
      cache: 'no-store',
    });
  }

  async getTopic(id: UUID): Promise<Topic> {
    return this.fetch<Topic>(`${API_ENDPOINTS.topics}/${id}`);
  }

  async createTopic(topic: TopicCreate): Promise<Topic> {
    return this.fetch<Topic>(API_ENDPOINTS.topics, {
      method: 'POST',
      body: JSON.stringify(topic),
    });
  }

  async updateTopic(id: UUID, topic: TopicUpdate): Promise<Topic> {
    return this.fetch<Topic>(`${API_ENDPOINTS.topics}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(topic),
    });
  }

  async deleteTopic(id: UUID): Promise<Topic> {
    return this.fetch<Topic>(`${API_ENDPOINTS.topics}/${id}`, {
      method: 'DELETE',
    });
  }
}
