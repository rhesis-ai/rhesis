import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Comment,
  CreateCommentRequest,
  UpdateCommentRequest,
  CommentReactionRequest,
} from '@/types/comments';

export class CommentsClient extends BaseApiClient {
  async getComments(entityType: string, entityId: string): Promise<Comment[]> {
    // Use the correct endpoint for getting comments by entity
    const response = await this.fetch<Comment[]>(
      `${API_ENDPOINTS.comments}/entity/${entityType}/${entityId}`
    );
    return response;
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
