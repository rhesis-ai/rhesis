import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { User, UserCreate, UserUpdate } from './interfaces/user';

export class UsersClient extends BaseApiClient {
  async getUsers(options: {
    skip?: number;
    limit?: number;
  } = {}): Promise<User[]> {
    const queryParams = new URLSearchParams();
    if (options.skip !== undefined) queryParams.append('skip', options.skip.toString());
    if (options.limit !== undefined) queryParams.append('limit', options.limit.toString());

    const queryString = queryParams.toString();
    const url = queryString ? `${API_ENDPOINTS.users}?${queryString}` : API_ENDPOINTS.users;

    return this.fetch<User[]>(url, {
      cache: 'no-store'
    });
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