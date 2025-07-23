import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { User, UserCreate, UserUpdate } from './interfaces/user';
import { joinUrl } from '@/utils/url';

export class UsersClient extends BaseApiClient {
  async getUsers(options: {
    skip?: number;
    limit?: number;
  } = {}): Promise<{ data: User[]; total: number }> {
    const queryParams = new URLSearchParams();
    if (options.skip !== undefined) queryParams.append('skip', options.skip.toString());
    if (options.limit !== undefined) queryParams.append('limit', options.limit.toString());

    const queryString = queryParams.toString();
    const url = queryString ? `${API_ENDPOINTS.users}?${queryString}` : API_ENDPOINTS.users;

    // Make the request manually to access headers
    const path = API_ENDPOINTS[url as keyof typeof API_ENDPOINTS] || url;
    const fullUrl = joinUrl(this.baseUrl, path);
    
    const response = await fetch(fullUrl, {
      headers: this.getHeaders(),
      credentials: 'include',
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json() as User[];
    const total = this.extractTotalCount(response);

    return { data, total };
  }

  async getUser(id: string): Promise<User> {
    return this.fetch<User>(`${API_ENDPOINTS.users}/${id}`);
  }

  async createUser(user: UserCreate): Promise<User> {
    return this.fetch<User>(API_ENDPOINTS.users, {
      method: 'POST',
      body: JSON.stringify(user),
    });
  }

  async updateUser(id: string, user: UserUpdate): Promise<User | { user: User; session_token: string }> {
    return this.fetch<User | { user: User; session_token: string }>(`${API_ENDPOINTS.users}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(user),
    });
  }

  async deleteUser(id: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.users}/${id}`, {
      method: 'DELETE',
    });
  }
} 