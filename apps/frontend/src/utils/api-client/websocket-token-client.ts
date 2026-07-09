import { BaseApiClient } from './base-client';

export interface WebSocketTokenResponse {
  token: string;
  expires_in: number;
}

/**
 * Client for `POST /ws/token`.
 *
 * Issues a short-lived (60 s), single-use WebSocket token that should be
 * used immediately to open a `/ws` connection. Using this token instead of
 * the long-lived session JWT keeps the credential out of server logs, browser
 * history, and referrer headers.
 */
export class WebSocketTokenClient extends BaseApiClient {
  async getWebSocketToken(): Promise<WebSocketTokenResponse> {
    return this.fetch<WebSocketTokenResponse>('/ws/token', {
      method: 'POST',
      cache: 'no-store',
    });
  }
}
