import { BaseApiClient } from './base-client';
import { API_ENDPOINTS, API_CONFIG } from './config';

export class ServicesClient extends BaseApiClient {
  async getGitHubContents(repo_url: string): Promise<string> {
    return this.fetch<string>(`${API_ENDPOINTS.services}/github/contents?repo_url=${encodeURIComponent(repo_url)}`);
  }

  async getOpenAIJson(prompt: string) {
    return this.fetch<any>(`${API_ENDPOINTS.services}/openai/json`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt: typeof prompt === 'string' ? prompt : JSON.stringify(prompt)
      })
    });
  }

  async getOpenAIChat(messages: Array<{ role: string; content: string }>) {
    return this.fetch<string>(`${API_ENDPOINTS.services}/openai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages,
        response_format: 'text'
      })
    });
  }
} 