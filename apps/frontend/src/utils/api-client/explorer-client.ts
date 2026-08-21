import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { joinUrl } from '@/utils/url';
import {
  EvaluateRequest,
  EvaluateResponse,
  ExplorerSettings,
  ExplorerSettingsUpdateRequest,
  ExplorerTestSet,
  ExplorerTestSetDetail,
  ExportExplorerTestSetResponse,
  GenerateOutputsRequest,
  GenerateOutputsResponse,
  ImportExplorerTestSetResponse,
  SuggestionPipelineEvent,
  SuggestionPipelineRequest,
  TestNode,
  TestNodeCreate,
  TestNodeUpdate,
  Topic,
  TopicCreate,
  TopicUpdate,
} from './interfaces/explorer';

/**
 * API client for Explorer (test tree) HTTP endpoints.
 *
 * Provides methods for managing test tree data within a TestSet,
 * including operations on topics and tests.
 */
export class ExplorerClient extends BaseApiClient {
  private getBasePath(testSetId: string): string {
    return `${API_ENDPOINTS.explorer}/${testSetId}`;
  }

  /** Reads one chunk, erroring out if none arrives within `idleTimeoutMs`. */
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

  // ===========================================================================
  // Explorer test set operations
  // ===========================================================================

  /**
   * List explorer test sets (flagged via explorer_row).
   * @param skip Pagination offset
   * @param limit Maximum number of records
   * @param sortBy Field to sort by
   * @param sortOrder Sort direction
   */
  async getExplorerTestSets(
    skip: number = 0,
    limit: number = 100,
    sortBy: string = 'created_at',
    sortOrder: string = 'desc'
  ): Promise<ExplorerTestSetDetail[]> {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    return this.fetch<ExplorerTestSetDetail[]>(
      `${API_ENDPOINTS.explorer}/?${params.toString()}`,
      { cache: 'no-store' }
    );
  }

  /**
   * Create a new explorer test set.
   * @param name Test set name
   * @param description Optional description
   */
  async createExplorerTestSet(
    name: string,
    description?: string
  ): Promise<ExplorerTestSet> {
    return this.fetch<ExplorerTestSet>(`${API_ENDPOINTS.explorer}/`, {
      method: 'POST',
      body: JSON.stringify({ name, description: description ?? null }),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Delete an explorer test set.
   * @param testSetId The test set identifier (UUID, nano_id, or slug)
   */
  async deleteExplorerTestSet(testSetId: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.explorer}/${testSetId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Delete multiple explorer test sets at once.
   * @param testSetIds Test set IDs to delete
   */
  async bulkDeleteExplorerTestSets(testSetIds: string[]): Promise<void> {
    await this.bulkDelete<void>(
      API_ENDPOINTS.explorer,
      'test_set_ids',
      testSetIds
    );
  }

  /**
   * Import from an existing regular test set into a new explorer test set.
   * @param sourceTestSetId Source test set identifier (UUID, nano_id, or slug)
   */
  async importExplorerTestSetFromSource(
    sourceTestSetId: string
  ): Promise<ImportExplorerTestSetResponse> {
    const encoded = encodeURIComponent(sourceTestSetId);
    return this.fetch<ImportExplorerTestSetResponse>(
      `${API_ENDPOINTS.explorer}/import/${encoded}`,
      { method: 'POST' }
    );
  }

  /**
   * Export an explorer test set to a new regular test set.
   * @param explorerTestSetId Explorer test set identifier (UUID, nano_id, or slug)
   */
  async exportRegularTestSetFromExplorer(
    explorerTestSetId: string
  ): Promise<ExportExplorerTestSetResponse> {
    const encoded = encodeURIComponent(explorerTestSetId);
    return this.fetch<ExportExplorerTestSetResponse>(
      `${API_ENDPOINTS.explorer}/export/${encoded}`,
      { method: 'POST' }
    );
  }

  async getExplorerSettings(testSetId: string): Promise<ExplorerSettings> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<ExplorerSettings>(`${basePath}/settings`, {
      cache: 'no-store',
    });
  }

  async updateExplorerSettings(
    testSetId: string,
    body: ExplorerSettingsUpdateRequest
  ): Promise<ExplorerSettings> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<ExplorerSettings>(`${basePath}/settings`, {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  /**
   * Get the full test tree for a test set.
   * Returns all nodes including both test nodes and topic markers.
   * @param testSetId The test set identifier (UUID, nano_id, or slug)
   */
  async getTree(testSetId: string): Promise<TestNode[]> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TestNode[]>(`${basePath}/tree`, {
      cache: 'no-store',
    });
  }

  // ===========================================================================
  // Topic Operations
  // ===========================================================================

  /**
   * Get all topics or children of a parent topic.
   * @param testSetId The test set identifier
   * @param parent Optional parent path to get children of
   */
  async getTopics(testSetId: string, parent?: string): Promise<Topic[]> {
    const basePath = this.getBasePath(testSetId);
    const queryParams = parent ? `?parent=${encodeURIComponent(parent)}` : '';
    return this.fetch<Topic[]>(`${basePath}/topics${queryParams}`, {
      cache: 'no-store',
    });
  }

  /**
   * Create a new topic.
   * @param testSetId The test set identifier
   * @param topic Topic data to create
   */
  async createTopic(testSetId: string, topic: TopicCreate): Promise<Topic> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<Topic>(`${basePath}/topics`, {
      method: 'POST',
      body: JSON.stringify(topic),
    });
  }

  /**
   * Update a topic (rename or move).
   * @param testSetId The test set identifier
   * @param topicPath The topic path to update
   * @param update Update data (new_name for rename, new_path for move)
   */
  async updateTopic(
    testSetId: string,
    topicPath: string,
    update: TopicUpdate
  ): Promise<Topic> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<Topic>(`${basePath}/topics/${topicPath}`, {
      method: 'PUT',
      body: JSON.stringify(update),
    });
  }

  /**
   * Delete a topic. Subtopics are removed; tests under the topic are moved to the parent.
   * @param testSetId The test set identifier
   * @param topicPath The topic path to delete (e.g. "Safety/Violence")
   */
  async deleteTopic(testSetId: string, topicPath: string): Promise<void> {
    const basePath = this.getBasePath(testSetId);
    await this.fetch<void>(`${basePath}/topics/${topicPath}`, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Test Operations
  // ===========================================================================

  /**
   * Get all tests in the test tree.
   * @param testSetId The test set identifier
   * @param topic Optional topic to filter by
   */
  async getTests(testSetId: string, topic?: string): Promise<TestNode[]> {
    const basePath = this.getBasePath(testSetId);
    const queryParams = topic ? `?topic=${encodeURIComponent(topic)}` : '';
    return this.fetch<TestNode[]>(`${basePath}/tests${queryParams}`, {
      cache: 'no-store',
    });
  }

  /**
   * Get a specific test by ID.
   * @param testSetId The test set identifier
   * @param testId The test node ID
   */
  async getTest(testSetId: string, testId: string): Promise<TestNode> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TestNode>(`${basePath}/tests/${testId}`, {
      cache: 'no-store',
    });
  }

  /**
   * Create a new test node.
   * @param testSetId The test set identifier
   * @param test Test data to create
   */
  async createTest(testSetId: string, test: TestNodeCreate): Promise<TestNode> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TestNode>(`${basePath}/tests`, {
      method: 'POST',
      body: JSON.stringify(test),
    });
  }

  /**
   * Update a test node.
   * @param testSetId The test set identifier
   * @param testId The test node ID
   * @param test Update data
   */
  async updateTest(
    testSetId: string,
    testId: string,
    test: TestNodeUpdate
  ): Promise<TestNode> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TestNode>(`${basePath}/tests/${testId}`, {
      method: 'PUT',
      body: JSON.stringify(test),
    });
  }

  /**
   * Delete a test node.
   * @param testSetId The test set identifier
   * @param testId The test node ID
   */
  async deleteTest(testSetId: string, testId: string): Promise<void> {
    const basePath = this.getBasePath(testSetId);
    await this.fetch<void>(`${basePath}/tests/${testId}`, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Outputs and evaluation
  // ===========================================================================

  /**
   * Generate outputs for tests by invoking the given endpoint.
   * @param testSetId The test set identifier
   * @param body Endpoint ID and optional test IDs to limit scope
   */
  async generateOutputs(
    testSetId: string,
    body: GenerateOutputsRequest
  ): Promise<GenerateOutputsResponse> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<GenerateOutputsResponse>(`${basePath}/generate_outputs`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Evaluate tests using the specified metrics.
   * @param testSetId The test set identifier
   * @param body Metric names and optional filters
   */
  async evaluate(
    testSetId: string,
    body: EvaluateRequest
  ): Promise<EvaluateResponse> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<EvaluateResponse>(`${basePath}/evaluate`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // ===========================================================================
  // Suggestions (non-persisted)
  // ===========================================================================

  /**
   * Unified suggestion pipeline: generate, invoke endpoint, and evaluate
   * in a single NDJSON stream. Events arrive as they complete — output
   * events stream immediately, and evaluation events interleave as they finish.
   */
  async suggestionPipeline(
    testSetId: string,
    body: SuggestionPipelineRequest,
    handlers: {
      onEvent: (event: SuggestionPipelineEvent) => void;
    }
  ): Promise<void> {
    const basePath = this.getBasePath(testSetId);
    const url = joinUrl(this.baseUrl, `${basePath}/suggestion_pipeline`);
    const headers = this.getHeaders();

    const response = await fetch(url, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const errorBody = await response.text();
      let message = `Pipeline request failed (${response.status})`;
      try {
        const parsed = JSON.parse(errorBody);
        if (parsed.detail) message = parsed.detail;
      } catch {
        // use default message
      }
      throw new Error(message);
    }

    for await (const event of this.readNdjsonStream(response)) {
      handlers.onEvent(event as SuggestionPipelineEvent);
    }
  }
}
