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
  sources?: Array<{
    source: string;
    name: string;
    description?: string;
  }>;
}

interface Test {
  prompt: TestPrompt;
  behavior: string;
  category: string;
  topic: string;
  metadata: TestMetadata;
}

import { DocumentMetadata } from './interfaces/documents';
import {
  GenerationConfig,
  SourceData,
  GenerateTestsRequest,
  GenerateTestsResponse,
} from './interfaces/test-set';

interface ChipState {
  label: string;
  description: string;
  active: boolean;
  category: 'behavior' | 'topic' | 'category' | 'scenario';
}

interface IterationMessage {
  content: string;
  timestamp: string;
  chip_states?: ChipState[];
}

interface GenerateTestConfigRequest {
  prompt: string;
  project_id?: string;
  previous_messages?: IterationMessage[];
}

interface TestConfigItem {
  name: string;
  description: string;
  active: boolean;
}

interface GenerateTestConfigResponse {
  behaviors: TestConfigItem[];
  topics: TestConfigItem[];
  categories: TestConfigItem[];
  scenarios: TestConfigItem[];
}

// Multi-turn test types
interface MultiTurnPrompt {
  goal: string;
  instructions: string[];
  restrictions: string[];
  scenarios: string[];
}

interface MultiTurnTest {
  prompt: MultiTurnPrompt;
  behavior: string;
  category: string;
  topic: string;
}

interface GenerateMultiTurnTestsRequest {
  generation_prompt: string;
  behavior?: string[];
  category?: string[];
  topic?: string[];
  num_tests?: number;
}

interface GenerateMultiTurnTestsResponse {
  tests: MultiTurnTest[];
}

interface TextResponse {
  text: string;
}

interface ExtractDocumentResponse {
  content: string;
  format: string;
}

// MCP Types
export interface MCPItem {
  id: string;
  url: string;
  title: string;
}

export interface MCPExtractResponse {
  content: string;
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

  async generateMultiTurnTests(
    request: GenerateMultiTurnTestsRequest
  ): Promise<GenerateMultiTurnTestsResponse> {
    return this.fetch<GenerateMultiTurnTestsResponse>(
      `${API_ENDPOINTS.services}/generate/multiturn-tests`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      }
    );
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

  /**
   * Search MCP server for items matching the query
   * @param query - Search query string
   * @param serverName - MCP server name (e.g., "notionApi")
   * @returns Array of MCP items with id, url, and title
   */
  async searchMCP(query: string, serverName: string): Promise<MCPItem[]> {
    return this.fetch<MCPItem[]>(`${API_ENDPOINTS.services}/mcp/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        server_name: serverName,
      }),
    });
  }

  /**
   * Extract full content from an MCP item as markdown
   * @param id - MCP item ID
   * @param serverName - MCP server name (e.g., "notionApi")
   * @returns Extracted content as markdown
   */
  async extractMCP(
    id: string,
    serverName: string
  ): Promise<MCPExtractResponse> {
    return this.fetch<MCPExtractResponse>(
      `${API_ENDPOINTS.services}/mcp/extract`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id,
          server_name: serverName,
        }),
      }
    );
  }
}
