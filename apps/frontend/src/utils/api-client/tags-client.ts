import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Tag, TagCreate, TagUpdate, EntityType } from './interfaces/tag';

export interface TagsResponse {
    tags: Tag[];
    totalCount: number;
}

export class TagsClient extends BaseApiClient {
    async getTags(options: {
        skip?: number;
        limit?: number;
        sort_by?: string;
        sort_order?: string;
    } = {}): Promise<Tag[]> {
        const queryParams = new URLSearchParams();
        if (options.skip !== undefined) queryParams.append('skip', options.skip.toString());
        if (options.limit !== undefined) queryParams.append('limit', options.limit.toString());
        if (options.sort_by) queryParams.append('sort_by', options.sort_by);
        if (options.sort_order) queryParams.append('sort_order', options.sort_order);

        const queryString = queryParams.toString();
        const url = queryString ? `${API_ENDPOINTS.tags}?${queryString}` : API_ENDPOINTS.tags;

        return this.fetch<Tag[]>(url, {
            cache: 'no-store'
        });
    }

    async getTag(id: string): Promise<Tag> {
        return this.fetch<Tag>(`${API_ENDPOINTS.tags}/${id}`);
    }

    async createTag(tag: TagCreate): Promise<Tag> {
        return this.fetch<Tag>(API_ENDPOINTS.tags, {
            method: 'POST',
            body: JSON.stringify(tag),
        });
    }

    async updateTag(id: string, tag: TagUpdate): Promise<Tag> {
        return this.fetch<Tag>(`${API_ENDPOINTS.tags}/${id}`, {
            method: 'PUT',
            body: JSON.stringify(tag),
        });
    }

    async deleteTag(id: string): Promise<Tag> {
        return this.fetch<Tag>(`${API_ENDPOINTS.tags}/${id}`, {
            method: 'DELETE',
        });
    }

    async assignTagToEntity(
        entityType: EntityType,
        entityId: string,
        tag: TagCreate
    ): Promise<Tag> {
        return this.fetch<Tag>(`${API_ENDPOINTS.tags}/${entityType}/${entityId}`, {
            method: 'POST',
            body: JSON.stringify(tag),
        });
    }

    async removeTagFromEntity(
        entityType: EntityType,
        entityId: string,
        tagId: string
    ): Promise<{ status: string }> {
        return this.fetch<{ status: string }>(
            `${API_ENDPOINTS.tags}/${entityType}/${entityId}/${tagId}`,
            {
                method: 'DELETE',
            }
        );
    }
}
