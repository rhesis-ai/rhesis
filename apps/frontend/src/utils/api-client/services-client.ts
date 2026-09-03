import {
  ApiErrorData,
  BaseApiClient,
  parseApiErrorResponse,
} from './base-client';
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
  requirement: string;
  category: string;
  topic: string;
  metadata: TestMetadata;
}

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
  category: 'requirement' | 'topic' | 'category' | 'scenario';
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
  requirements: TestConfigItem[];
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
  requirement: string;
  category: string;
  topic: string;
}

interface GenerateMultiTurnTestsRequest {
  generation_prompt: string;
  // Plural, matching the backend GenerationConfig. The backend still accepts the
  // old singular spellings as aliases, but new callers should not use them.
  requirements?: string[];
  categories?: string[];
  topics?: string[];
  num_tests?: number;
  model_id?: string; // Override user's default generation model for this request
}

interface GenerateMultiTurnTestsResponse {
  tests: MultiTurnTest[];
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
  tool_metadata?: Record<string, unknown>;
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
  /** Reads one chunk, erroring out if none arrives within `idleTimeoutMs`.
   * Mirrors `ExplorerClient`'s identical guard on the same NDJSON pattern. */
  private async readChunkWithTimeout(
    reader: ReadableStreamDefaultReader<Uint8Array>,
    idleTimeoutMs: number
  ): Promise<ReadableStreamReadResult<Uint8Array>> {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => {
        reader.cancel().catch(() => {});
        reject(
          new Error(
            `Stream stalled: no data received for ${idleTimeoutMs / 1000}s.`
          )
        );
      }, idleTimeoutMs);
    });
    try {
      return await Promise.race([reader.read(), timeout]);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private async *readNdjsonStream(
    response: Response,
    idleTimeoutMs = 150_000
  ): AsyncGenerator<unknown, void, void> {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Streaming response body is not available.');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await this.readChunkWithTimeout(
        reader,
        idleTimeoutMs
      );
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
      // Same shape BaseApiClient's own fetch() throws (status/data attached,
      // "API error: {status} - " prefix): getApiErrorMessage() strips that
      // prefix and parseQuotaError() reads .status/.data, and this request
      // goes through fetch() directly rather than that shared path, so
      // without this a 402 (require_quota on the route this streams from)
      // showed the raw JSON body in a toast instead of the quota sentence.
      const bodyText = await response.text();
      let errorData: ApiErrorData = {};
      try {
        errorData = JSON.parse(bodyText) as ApiErrorData;
      } catch {
        // Not JSON; parseApiErrorResponse falls back to stringifying {}.
      }
      const message = parseApiErrorResponse(errorData) || bodyText;
      const error = new Error(
        `API error: ${response.status} - ${message}`
      ) as Error & {
        status?: number;
        data?: ApiErrorData;
      };
      error.status = response.status;
      error.data = errorData;
      throw error;
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
