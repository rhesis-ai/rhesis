import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Token, TokenResponse } from './interfaces/token';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

export class TokensClient extends BaseApiClient {
  async createToken(
    name: string,
    expiresInDays: number | null
  ): Promise<TokenResponse> {
    return this.fetch<TokenResponse>(API_ENDPOINTS.tokens, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, expires_in_days: expiresInDays }),
    });
  }

  async listTokens(
    params?: PaginationParams
  ): Promise<PaginatedResponse<Token>> {
    try {
      return this.fetchPaginated<Token>(API_ENDPOINTS.tokens, {
        skip: params?.skip || 0,
        limit: params?.limit || 10,
        sort_by: params?.sort_by || 'created_at',
        sort_order: params?.sort_order || 'desc',
      });
    } catch (_error) {
      return {
        data: [],
        pagination: {
          totalCount: 0,
          skip: params?.skip || 0,
          limit: params?.limit || 10,
          currentPage: 0,
          pageSize: params?.limit || 10,
          totalPages: 0,
        },
      };
    }
  }

  async deleteToken(tokenId: string): Promise<Token> {
    return this.fetch<Token>(`${API_ENDPOINTS.tokens}/${tokenId}`, {
      method: 'DELETE',
    });
  }

  async refreshToken(
    tokenId: string,
    expiresInDays: number | null
  ): Promise<TokenResponse> {
    return this.fetch<TokenResponse>(
      `${API_ENDPOINTS.tokens}/${tokenId}/refresh`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ expires_in_days: expiresInDays }),
      }
    );
  }
}
