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
  TestPipelineEvent,
  TestPipelineRequest,
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
  model_id?: string; // Override user's default generation model for this request
}

interface GenerateMultiTurnTestsResponse {
  tests: MultiTurnTest[];
}

interface TextResponse {
  text: string;
}

// Tool Types
export interface ToolItem {
  id: string;
  url: string;
  title: string;
}

export interface ToolExtractResponse {
  content: string;
}

export interface ExtractedSource {
  id?: string;
  title?: string;
  content: string;
  url?: string;
}

export interface ExtractToolResponse {
  sources: ExtractedSource[];
}

export interface TestToolConnectionRequest {
  tool_id?: string;
  provider_type_id?: string;
  credentials?: Record<string, string>;
}

export interface TestToolConnectionResponse {
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
  private async *readNdjsonStream(
    response: Response
  ): AsyncGenerator<unknown, void, void> {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Streaming response body is not available.');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIndex = buffer.indexOf('\n');
      while (newlineIndex !== -1) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        if (line) {
          yield JSON.parse(line) as unknown;
        }
        newlineIndex = buffer.indexOf('\n');
      }
    }

    const remaining = buffer.trim();
    if (remaining) {
      yield JSON.parse(remaining) as unknown;
    }
  }

  async generateTestPipelineStream(
    request: TestPipelineRequest,
    options: {
      onEvent: (event: TestPipelineEvent) => void;
      signal?: AbortSignal;
    }
  ): Promise<void> {
    const headers = this.getHeaders();
    const response = await fetch(
      `${this.baseUrl}${API_ENDPOINTS.services}/generate/test_pipeline`,
      {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: options.signal,
      }
    );

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(
        `Test pipeline request failed (${response.status}): ${errorBody}`
      );
    }

    for await (const event of this.readNdjsonStream(response)) {
      options.onEvent(event as TestPipelineEvent);
    }
  }

  async getGitHubContents(repo_url: string): Promise<string> {
    return this.fetch<string>(
      `${API_ENDPOINTS.services}/github/contents?repo_url=${encodeURIComponent(repo_url)}`
    );
  }

  async getOpenAIJson(prompt: string): Promise<Record<string, unknown>> {
    return this.fetch<Record<string, unknown>>(
      `${API_ENDPOINTS.services}/openai/json`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: typeof prompt === 'string' ? prompt : JSON.stringify(prompt),
        }),
      }
    );
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
   * Extract content from a tool item (Notion page, GitHub file/dir) via the
   * deterministic REST path. Returns one source per page/file.
   */
  async extractTool(
    toolId: string,
    options: { url?: string; id?: string; include_children?: boolean }
  ): Promise<ExtractToolResponse> {
    return this.fetch<ExtractToolResponse>(
      `${API_ENDPOINTS.tools}/${toolId}/extract`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
      }
    );
  }

  /**
   * Test tool credentials via lightweight REST health check
   */
  async testToolConnection(
    request: TestToolConnectionRequest
  ): Promise<TestToolConnectionResponse> {
    return this.fetch<TestToolConnectionResponse>(
      `${API_ENDPOINTS.tools}/test-connection`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      `${API_ENDPOINTS.tools}/jira/create-ticket-from-task`,
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
