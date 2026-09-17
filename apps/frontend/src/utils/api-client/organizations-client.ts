import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Organization,
  OrganizationSettings,
  OrganizationSettingsRead,
  OrganizationSettingsUpdate,
} from './interfaces/organization';
import { UUID } from 'crypto';

export type OrganizationCreate = Omit<Organization, 'id' | 'createdAt'> & {
  owner_id: string;
  user_id: string;
};

export class OrganizationsClient extends BaseApiClient {
  constructor(sessionToken?: string, retryConfig = {}, projectId?: string) {
    super(sessionToken, retryConfig, projectId);
  }

  async getOrganizations(): Promise<Organization[]> {
    return this.fetch<Organization[]>(`${API_ENDPOINTS.organizations}/`, {
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
      return await this.fetch<Organization>(`${API_ENDPOINTS.organizations}/`, {
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
    // id/nano_id are backend-assigned and ignored in request bodies; the organization is
    // addressed by the id path param instead.
    data: Omit<Partial<Organization>, 'id' | 'nano_id'>
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

  // --- Organization settings ------------------------------------------------
  //
  // Branding lives in `organization_settings`, which `getOrganization` already
  // returns. These endpoints exist because writes need validation and the
  // asset uploads need multipart — see the backend's organization router.

  async getOrganizationSettings(): Promise<OrganizationSettingsRead> {
    return this.fetch<OrganizationSettingsRead>(
      `${API_ENDPOINTS.organizations}/settings`,
      { cache: 'no-store' }
    );
  }

  /**
   * Partial update, deep merged server-side. Send only what changed; an
   * explicit `null` clears a field back to the deployment default.
   */
  async updateOrganizationSettings(
    settings: OrganizationSettingsUpdate
  ): Promise<OrganizationSettings> {
    return this.fetch<OrganizationSettings>(
      `${API_ENDPOINTS.organizations}/settings`,
      {
        method: 'PATCH',
        body: JSON.stringify(settings),
      }
    );
  }

  /**
   * Family names published on Google Fonts, for the branding form's picker.
   * Empty when the catalogue is unreachable — the field still accepts any
   * family, and the backend verifies it on save.
   */
  async getGoogleFontFamilies(): Promise<string[]> {
    return this.fetch<string[]>(
      `${API_ENDPOINTS.organizations}/settings/branding/google-fonts`
    );
  }

  async uploadBrandingFavicon(file: File): Promise<OrganizationSettings> {
    const formData = new FormData();
    formData.append('file', file);
    return this.postBrandingForm('favicon', formData);
  }

  async deleteBrandingFavicon(): Promise<OrganizationSettings> {
    return this.fetch<OrganizationSettings>(
      `${API_ENDPOINTS.organizations}/settings/branding/favicon`,
      { method: 'DELETE' }
    );
  }

  /**
   * Upload a brand font. `files` maps a weight ('300' | '400' | '700') to the
   * file for it; weights left out are simply not uploaded, and the browser
   * synthesises them from the nearest one available.
   */
  async uploadBrandingFont(
    family: string,
    files: Partial<Record<'300' | '400' | '700', File>>
  ): Promise<OrganizationSettings> {
    const formData = new FormData();
    formData.append('family', family);
    for (const [weight, file] of Object.entries(files)) {
      if (file) formData.append(`weight_${weight}`, file);
    }
    return this.postBrandingForm('font', formData);
  }

  /**
   * Multipart POST to a branding asset endpoint.
   *
   * Bypasses `this.fetch` because that sets `Content-Type: application/json`;
   * multipart needs the browser to set it, boundary and all.
   */
  private async postBrandingForm(
    asset: 'favicon' | 'font',
    formData: FormData
  ): Promise<OrganizationSettings> {
    const url = `${this.baseUrl}${API_ENDPOINTS.organizations}/settings/branding/${asset}`;

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: { ...this.buildAuthHeaders() },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error('Unauthorized');
      }
      throw new Error(await extractErrorMessage(response));
    }

    return response.json();
  }
}

/** Pull a readable message out of a failed response, JSON `detail` or plain text. */
async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      const data: unknown = await response.json();
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail: unknown }).detail;
        if (typeof detail === 'string') return detail;
      }
      return JSON.stringify(data);
    }
    return (await response.text()) || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}
