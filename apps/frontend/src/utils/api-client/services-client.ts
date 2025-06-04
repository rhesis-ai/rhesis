import { BaseApiClient } from './base-client';
import { API_ENDPOINTS, API_CONFIG } from './config';

// Types for the new endpoints - matching backend schemas
interface TestPrompt {
  content: string;
  language_code: string;
}

interface TestMetadata {
  generated_by: string;
  additional_info?: Record<string, any>;
}

interface Test {
  prompt: TestPrompt;
  behavior: string;
  category: string;
  topic: string;
  metadata: TestMetadata;
}

interface GenerateTestsRequest {
  prompt: string;
  num_tests?: number;
}

interface GenerateTestsResponse {
  tests: Test[];
}

interface TextResponse {
  text: string;
}

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

  async generateText(prompt: string, stream: boolean = false): Promise<TextResponse> {
    return this.fetch<TextResponse>(`${API_ENDPOINTS.services}/generate/text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt,
        stream
      })
    });
  }

  async generateTests(request: GenerateTestsRequest): Promise<GenerateTestsResponse> {
    return this.fetch<GenerateTestsResponse>(`${API_ENDPOINTS.services}/generate/tests`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    });
  }
} 