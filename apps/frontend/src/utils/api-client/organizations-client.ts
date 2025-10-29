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
    } catch (error: any) {
      // Extract useful error message or use a default
      const errorMessage =
        error.data?.detail ||
        error.data?.message ||
        (error.message
          ? error.message.replace(/^API error: \d+ - /, '')
          : 'Failed to create organization');

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
