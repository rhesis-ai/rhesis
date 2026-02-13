import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';

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
  additional_info?: Record<string, unknown>;
  sources?: Array<{
    source: string;
    name: string;
    description?: string;
  }>;
}

interface _Test {
  prompt: TestPrompt;
  behavior: string;
  category: string;
  topic: string;
  metadata: TestMetadata;
}

import { RecentActivitiesResponse } from './interfaces/activities';
import {
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

// MCP Types
export interface MCPItem {
  id: string;
  url: string;
  title: string;
}

export interface MCPExtractResponse {
  content: string;
}

export interface TestMCPConnectionRequest {
  tool_id?: string;
  provider_type_id?: string;
  credentials?: Record<string, string>;
  tool_metadata?: Record<string, unknown>;
}

export interface TestMCPConnectionResponse {
  is_authenticated: string; // "Yes" or "No"
  message: string;
  additional_metadata?: {
    projects?: Array<{ key: string; name: string }>;
    spaces?: Array<{ key: string; name: string }>;
    [key: string]: unknown;
  };
}

export interface CreateJiraTicketFromTaskRequest {
  task_id: string;
  tool_id: string;
}

export interface CreateJiraTicketFromTaskResponse {
  issue_key: string;
  issue_url: string;
  message: string;
}

export class ServicesClient extends BaseApiClient {
  async getGitHubContents(repo_url: string): Promise<string> {
    return this.fetch<string>(
      `${API_ENDPOINTS.services}/github/contents?repo_url=${encodeURIComponent(repo_url)}`
    );
  }

  async getOpenAIJson(prompt: string): Promise<Record<string, unknown>> {
    return this.fetch<Record<string, unknown>>(`${API_ENDPOINTS.services}/openai/json`, {
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

  /**
   * Search MCP server for items matching the query
   * @param query - Search query string
   * @param toolId - ID of the configured tool integration
   * @returns Array of MCP items with id, url, and title
   */
  async searchMCP(query: string, toolId: string): Promise<MCPItem[]> {
    return this.fetch<MCPItem[]>(`${API_ENDPOINTS.services}/mcp/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        tool_id: toolId,
      }),
    });
  }

  /**
   * Extract full content from an MCP item as markdown
   * @param options - Either { url: string } or { id: string } (or both), plus toolId
   * @param toolId - ID of the configured tool integration
   * @returns Extracted content as markdown
   */
  async extractMCP(
    options: { url?: string; id?: string },
    toolId: string
  ): Promise<MCPExtractResponse> {
    return this.fetch<MCPExtractResponse>(
      `${API_ENDPOINTS.services}/mcp/extract`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...options,
          tool_id: toolId,
        }),
      }
    );
  }

  /**
   * Test MCP connection authentication
   * @param request - Either tool_id (for existing tools) OR provider_type_id + credentials + optional tool_metadata (for non-existent tools)
   * @returns Test result with authentication status and message
   */
  async testMCPConnection(
    request: TestMCPConnectionRequest
  ): Promise<TestMCPConnectionResponse> {
    return this.fetch<TestMCPConnectionResponse>(
      `${API_ENDPOINTS.services}/mcp/test-connection`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      }
    );
  }

  /**
   * Get recent activities across all trackable entities
   * @param limit - Maximum number of activities to return (default 50, max 200)
   * @returns Promise with activities list and total count
   */
  async getRecentActivities(
    limit: number = 50
  ): Promise<RecentActivitiesResponse> {
    return this.fetch<RecentActivitiesResponse>(
      `${API_ENDPOINTS.services}/recent-activities?limit=${limit}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }

  /**
   * Create a Jira ticket from a task
   * @param taskId - ID of the task to create a ticket from
   * @param toolId - ID of the Jira MCP tool integration
   * @returns Promise with issue key, URL, and message
   */
  async createJiraTicketFromTask(
    taskId: string,
    toolId: string
  ): Promise<CreateJiraTicketFromTaskResponse> {
    return this.fetch<CreateJiraTicketFromTaskResponse>(
      `${API_ENDPOINTS.services}/mcp/jira/create-ticket-from-task`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: taskId,
          tool_id: toolId,
        }),
      }
    );
  }
}
