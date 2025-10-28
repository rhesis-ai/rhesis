import { BaseApiClient } from './base-client';
import { API_ENDPOINTS, API_CONFIG } from './config';

// Types for the new endpoints - matching backend schemas
interface TestPrompt {
  content: string;
  language_code: string;
  demographic?: string;
  dimension?: string;
  expected_response?: string;
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

import {
  Document,
  DocumentUploadResponse,
  DocumentMetadata,
} from './interfaces/documents';

interface GenerateTestsRequest {
  prompt: object;
  num_tests?: number;
  documents?: Document[];
  // Iteration context - same as test config
  chip_states?: ChipState[];
  rated_samples?: RatedSample[];
  previous_messages?: IterationMessage[];
}

interface GenerateTestsResponse {
  tests: Test[];
}

interface ChipState {
  label: string;
  description: string;
  active: boolean;
  category: 'behavior' | 'topic' | 'category' | 'scenario';
}

interface RatedSample {
  prompt: string;
  response: string;
  rating: number;
  feedback?: string;
}

interface IterationMessage {
  content: string;
  timestamp: string;
  chip_states?: ChipState[];
}

interface GenerateTestConfigRequest {
  prompt: string;
  sample_size: number;
  project_id?: string;
  // Iteration context
  chip_states?: ChipState[];
  rated_samples?: RatedSample[];
  previous_messages?: IterationMessage[];
}

interface TestConfigItem {
  name: string;
  description: string;
}

interface GenerateTestConfigResponse {
  behaviors: TestConfigItem[];
  topics: TestConfigItem[];
  categories: TestConfigItem[];
  scenarios: TestConfigItem[];
}

interface TextResponse {
  text: string;
}

interface ExtractDocumentResponse {
  content: string;
  format: string;
}

export class ServicesClient extends BaseApiClient {
  async getGitHubContents(repo_url: string): Promise<string> {
    return this.fetch<string>(
      `${API_ENDPOINTS.services}/github/contents?repo_url=${encodeURIComponent(repo_url)}`
    );
  }

  async getOpenAIJson(prompt: string) {
    return this.fetch<any>(`${API_ENDPOINTS.services}/openai/json`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: typeof prompt === 'string' ? prompt : JSON.stringify(prompt),
      }),
    });
  }

  async getOpenAIChat(messages: Array<{ role: string; content: string }>) {
    return this.fetch<string>(`${API_ENDPOINTS.services}/openai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages,
        response_format: 'text',
      }),
    });
  }

  async generateText(
    prompt: string,
    stream: boolean = false
  ): Promise<TextResponse> {
    return this.fetch<TextResponse>(`${API_ENDPOINTS.services}/generate/text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt,
        stream,
      }),
    });
  }

  async generateTests(
    request: GenerateTestsRequest
  ): Promise<GenerateTestsResponse> {
    return this.fetch<GenerateTestsResponse>(
      `${API_ENDPOINTS.services}/generate/tests`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      }
    );
  }

  async generateTestConfig(
    request: GenerateTestConfigRequest
  ): Promise<GenerateTestConfigResponse> {
    return this.fetch<GenerateTestConfigResponse>(
      `${API_ENDPOINTS.services}/generate/test_config`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      }
    );
  }

  async uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('document', file);

    // For multipart/form-data, we need to override the default headers
    // Create headers object without Content-Type so browser can set it correctly
    const headers: Record<string, string> = {};

    // Add authorization if we have a session token (copied from BaseApiClient logic)
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    // Use direct fetch to avoid BaseApiClient's default Content-Type header
    const path = `${this.baseUrl}/services/documents/upload`;
    const response = await fetch(path, {
      method: 'POST',
      body: formData,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = '';
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || 'Upload failed';
      } catch {
        errorMessage = await response.text();
      }
      throw new Error(`API error: ${response.status} - ${errorMessage}`);
    }

    return response.json() as Promise<DocumentUploadResponse>;
  }

  async generateDocumentMetadata(content: string): Promise<DocumentMetadata> {
    const structuredPrompt = `
    Generate a concise name and description for this document content.
    Format your response exactly like this:
    Name: <a clear, concise title for the document>
    Description: <a brief description of the document's content>

    Document content: ${content}
  `;

    const response = await this.generateText(structuredPrompt);

    try {
      // First try to find the name and description using the structured format
      const nameMatch = response.text.match(
        /Name:\s*([\s\S]+?)(?=\n|Description:|$)/
      );
      const descriptionMatch = response.text.match(
        /Description:\s*([\s\S]+?)(?=\n|$)/
      );

      return {
        name: (nameMatch?.[1] || '').trim() || 'Untitled Document',
        description: (descriptionMatch?.[1] || '').trim() || '',
      };
    } catch {
      // Fallback to the old method if parsing fails
      return {
        name: 'Untitled Document',
        description: '',
      };
    }
  }

  async extractDocument(path: string): Promise<ExtractDocumentResponse> {
    return this.fetch<ExtractDocumentResponse>(
      `${API_ENDPOINTS.services}/documents/extract`,
      {
        method: 'POST',
        body: JSON.stringify({ path }),
      }
    );
  }
}
