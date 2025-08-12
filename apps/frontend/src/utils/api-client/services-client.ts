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

interface DocumentUploadResponse {
  path: string;
}

interface DocumentMetadata {
  name: string;
  description: string;
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
      credentials: 'include'
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
    const response = await this.generateText(`Generate a concise name and description for this document content: ${content}`);
    
    try {
      const parsed = JSON.parse(response.text);
      return {
        name: parsed.name || 'Untitled Document',
        description: parsed.description || ''
      };
    } catch {
      const lines = response.text.split('\n');
      return {
        name: lines[0] || 'Untitled Document',
        description: lines.slice(1).join('\n') || ''
      };
    }
  }

} 