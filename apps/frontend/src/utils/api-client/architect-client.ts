import { BaseApiClient } from './base-client';

export interface ArchitectSession {
  id: string;
  nano_id?: string;
  title?: string;
  mode?: string;
  plan_data?: Record<string, unknown>;
  agent_state?: Record<string, unknown>;
  user_id?: string;
  organization_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ArchitectSessionDetail extends ArchitectSession {
  messages: ArchitectMessageResponse[];
}

export interface ArchitectMessageResponse {
  id: string;
  nano_id?: string;
  session_id: string;
  role: string;
  content?: string;
  metadata_?: Record<string, unknown>;
  attachments?: Record<string, unknown>;
  created_at?: string;
}

export interface ArchitectSessionCreateRequest {
  title?: string;
}

export class ArchitectClient extends BaseApiClient {
  private basePath = '/architect/sessions';

  async getSessions(
    skip = 0,
    limit = 20
  ): Promise<ArchitectSession[]> {
    return this.fetch<ArchitectSession[]>(
      `${this.basePath}?skip=${skip}&limit=${limit}&sort_by=updated_at&sort_order=desc`
    );
  }

  async createSession(
    data?: ArchitectSessionCreateRequest
  ): Promise<ArchitectSession> {
    return this.fetch<ArchitectSession>(this.basePath, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    });
  }

  async getSession(id: string): Promise<ArchitectSessionDetail> {
    return this.fetch<ArchitectSessionDetail>(`${this.basePath}/${id}`);
  }

  async deleteSession(id: string): Promise<void> {
    await this.fetch<ArchitectSession>(`${this.basePath}/${id}`, {
      method: 'DELETE',
    });
  }

  async getMessages(
    sessionId: string,
    skip = 0,
    limit = 100
  ): Promise<ArchitectMessageResponse[]> {
    return this.fetch<ArchitectMessageResponse[]>(
      `${this.basePath}/${sessionId}/messages?skip=${skip}&limit=${limit}`
    );
  }
}
