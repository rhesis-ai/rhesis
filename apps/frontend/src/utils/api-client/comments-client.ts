import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Comment,
  CreateCommentRequest,
  UpdateCommentRequest,
} from '@/types/comments';

export class CommentsClient extends BaseApiClient {
  async getComments(entityType: string, entityId: string): Promise<Comment[]> {
    // Fetch all comments by paginating through all pages
    // Backend has a 100 limit, so we need to fetch in batches
    const allComments: Comment[] = [];
    let skip = 0;
    const limit = 100; // Backend maximum limit

    while (true) {
      const response = await this.fetch<Comment[]>(
        `${API_ENDPOINTS.comments}/entity/${entityType}/${entityId}?skip=${skip}&limit=${limit}`
      );

      allComments.push(...response);

      // If we got fewer comments than the limit, we've reached the end
      if (response.length < limit) {
        break;
      }

      skip += limit;
    }

    return allComments;
  }

  async createComment(data: CreateCommentRequest): Promise<Comment> {
    const response = await this.fetch<Comment>(API_ENDPOINTS.comments, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response;
  }

  async updateComment(
    commentId: string,
    data: UpdateCommentRequest
  ): Promise<Comment> {
    const response = await this.fetch<Comment>(
      `${API_ENDPOINTS.comments}/${commentId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    );
    return response;
  }

  async deleteComment(commentId: string): Promise<Comment> {
    return this.fetch<Comment>(`${API_ENDPOINTS.comments}/${commentId}`, {
      method: 'DELETE',
    });
  }

  async addEmojiReaction(commentId: string, emoji: string): Promise<Comment> {
    const response = await this.fetch<Comment>(
      `${API_ENDPOINTS.comments}/${commentId}/emoji/${emoji}`,
      {
        method: 'POST',
      }
    );
    return response;
  }

  async removeEmojiReaction(
    commentId: string,
    emoji: string
  ): Promise<Comment> {
    const response = await this.fetch<Comment>(
      `${API_ENDPOINTS.comments}/${commentId}/emoji/${emoji}`,
      {
        method: 'DELETE',
      }
    );
    return response;
  }
}
