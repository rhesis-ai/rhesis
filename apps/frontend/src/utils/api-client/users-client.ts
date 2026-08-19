import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  User,
  UserCreate,
  UserUpdate,
  UserSettings,
  UserSettingsUpdate,
} from './interfaces/user';
import { PaginatedResponse } from './interfaces/pagination';

export class UsersClient extends BaseApiClient {
  async getUsers(
    options: {
      skip?: number;
      limit?: number;
      /** OData filter expression (sent as `$filter` query param). */
      $filter?: string;
    } = {}
  ): Promise<PaginatedResponse<User>> {
    return this.fetchPaginated<User>(
      API_ENDPOINTS.users,
      {
        skip: options.skip ?? 0,
        limit: options.limit ?? 10,
        $filter: options.$filter,
      },
      { cache: 'no-store' }
    );
  }

  async getUser(id: string): Promise<User> {
    return this.fetch<User>(`${API_ENDPOINTS.users}/${id}`);
  }

  async createUser(user: UserCreate): Promise<User> {
    return this.fetch<User>(`${API_ENDPOINTS.users}/`, {
      method: 'POST',
      body: JSON.stringify(user),
    });
  }

  async updateUser(
    id: string,
    user: UserUpdate
  ): Promise<User | { user: User; session_token: string }> {
    return this.fetch<User | { user: User; session_token: string }>(
      `${API_ENDPOINTS.users}/${id}`,
      {
        method: 'PUT',
        body: JSON.stringify(user),
      }
    );
  }

  async deleteUser(id: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.users}/${id}`, {
      method: 'DELETE',
    });
  }

  async leaveOrganization(): Promise<User> {
    return this.fetch<User>(`${API_ENDPOINTS.users}/leave-organization`, {
      method: 'PATCH',
    });
  }

  /**
   * Get current user's settings
   * @returns Current user settings including model preferences, UI settings, notifications, etc.
   */
  async getUserSettings(): Promise<UserSettings> {
    return this.fetch<UserSettings>(`${API_ENDPOINTS.users}/settings`);
  }

  /**
   * Update user settings with partial data (deep merge)
   * @param settings Partial settings to update. Only send the fields you want to change.
   * @returns Updated complete user settings
   * @example
   * // Update only UI theme
   * await updateUserSettings({ ui: { theme: 'dark' } });
   *
   * // Update generation model
   * await updateUserSettings({
   *   models: {
   *     generation: {
   *       model_id: '550e8400-e29b-41d4-a716-446655440000',
   *       temperature: 0.7
   *     }
   *   }
   * });
   */
  async updateUserSettings(
    settings: UserSettingsUpdate
  ): Promise<UserSettings> {
    return this.fetch<UserSettings>(`${API_ENDPOINTS.users}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }
}
