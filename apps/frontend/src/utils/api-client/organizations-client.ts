import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Organization } from './interfaces/organization';
import { UUID } from 'crypto';

export type OrganizationCreate = Omit<Organization, 'id' | 'createdAt'> & {
  owner_id: string;
  user_id: string;
};

export class OrganizationsClient extends BaseApiClient {
  constructor(sessionToken: string) {
    super(sessionToken);
  }

  async getOrganizations(): Promise<Organization[]> {
    return this.fetch<Organization[]>(API_ENDPOINTS.organizations, {
      cache: 'no-store',
    });
  }

  async getOrganization(identifier: UUID | string): Promise<Organization> {
    return this.fetch<Organization>(
      `${API_ENDPOINTS.organizations}/${identifier}`
    );
  }

  async createOrganization(
    organization: OrganizationCreate
  ): Promise<Organization> {
    try {
      return await this.fetch<Organization>(API_ENDPOINTS.organizations, {
        method: 'POST',
        body: JSON.stringify(organization),
      });
    } catch (error: unknown) {
      let errorMessage = 'Failed to create organization';
      if (error && typeof error === 'object') {
        const err = error as Record<string, unknown>;
        const data = err.data as Record<string, unknown> | undefined;
        if (typeof data?.detail === 'string') {
          errorMessage = data.detail;
        } else if (typeof data?.message === 'string') {
          errorMessage = data.message;
        } else if (typeof err.message === 'string') {
          errorMessage = err.message.replace(/^API error: \d+ - /, '');
        }
      }
      throw new Error(errorMessage);
    }
  }

  async updateOrganization(
    id: UUID | string,
    data: Partial<Organization>
  ): Promise<Organization> {
    return this.fetch<Organization>(`${API_ENDPOINTS.organizations}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteOrganization(id: UUID | string): Promise<void> {
    return this.fetch(`${API_ENDPOINTS.organizations}/${id}`, {
      method: 'DELETE',
    });
  }

  async loadInitialData(
    id: UUID | string
  ): Promise<{ status: string; message: string }> {
    return this.fetch(
      `${API_ENDPOINTS.organizations}/${id}/load-initial-data`,
      {
        method: 'POST',
      }
    );
  }
}
