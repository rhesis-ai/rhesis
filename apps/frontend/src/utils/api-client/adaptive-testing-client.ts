import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { joinUrl } from '@/utils/url';
import {
  AdaptiveTestSet,
  ExportAdaptiveTestSetResponse,
  ImportAdaptiveTestSetResponse,
  TestNode,
  TestNodeCreate,
  TestNodeUpdate,
  Topic,
  TopicCreate,
  TopicUpdate,
  TreeValidation,
  TreeStats,
  DeleteTopicResponse,
  DeleteTestResponse,
  GenerateOutputsRequest,
  GenerateOutputsResponse,
  EvaluateRequest,
  EvaluateResponse,
  GenerateSuggestionsRequest,
  GenerateSuggestionsResponse,
  GenerateSuggestionOutputsRequest,
  GenerateSuggestionOutputsResponse,
  SuggestionOutputStreamEvent,
  SuggestionEvalStreamEvent,
  EvaluateSuggestionsRequest,
  EvaluateSuggestionsResponse,
  AdaptiveSettings,
  AdaptiveSettingsUpdateRequest,
  SuggestionPipelineRequest,
  SuggestionPipelineEvent,
} from './interfaces/adaptive-testing';

/**
 * API client for adaptive testing CRUD operations.
 *
 * Provides methods for managing test tree data within a TestSet,
 * including operations on topics and tests.
 */
export class AdaptiveTestingClient extends BaseApiClient {
  private getBasePath(testSetId: string): string {
    return `${API_ENDPOINTS.adaptiveTesting}/${testSetId}`;
  }

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

  // ===========================================================================
  // Adaptive Test Set Operations
  // ===========================================================================

  /**
   * List all test sets configured for adaptive testing.
   * @param skip Pagination offset
   * @param limit Maximum number of records
   * @param sortBy Field to sort by
   * @param sortOrder Sort direction
   */
  async getAdaptiveTestSets(
    skip: number = 0,
    limit: number = 100,
    sortBy: string = 'created_at',
    sortOrder: string = 'desc'
  ): Promise<AdaptiveTestSet[]> {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    return this.fetch<AdaptiveTestSet[]>(
      `${API_ENDPOINTS.adaptiveTesting}?${params.toString()}`,
      { cache: 'no-store' }
    );
  }

  /**
   * Create a new test set configured for adaptive testing.
   * @param name Test set name
   * @param description Optional description
   */
  async createAdaptiveTestSet(
    name: string,
    description?: string
  ): Promise<AdaptiveTestSet> {
    return this.fetch<AdaptiveTestSet>(API_ENDPOINTS.adaptiveTesting, {
      method: 'POST',
      body: JSON.stringify({ name, description: description ?? null }),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Delete a test set configured for adaptive testing.
   * @param testSetId The test set identifier (UUID, nano_id, or slug)
   */
  async deleteAdaptiveTestSet(testSetId: string): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.adaptiveTesting}/${testSetId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Create a new adaptive test set by importing from an existing regular test set.
   * @param sourceTestSetId Source test set identifier (UUID, nano_id, or slug)
   */
  async importAdaptiveTestSetFromSource(
    sourceTestSetId: string
  ): Promise<ImportAdaptiveTestSetResponse> {
    const encoded = encodeURIComponent(sourceTestSetId);
    return this.fetch<ImportAdaptiveTestSetResponse>(
      `${API_ENDPOINTS.adaptiveTesting}/import/${encoded}`,
      { method: 'POST' }
    );
  }

  /**
   * Create a new regular test set by exporting from an adaptive test set.
   * @param adaptiveTestSetId Adaptive test set identifier (UUID, nano_id, or slug)
   */
  async exportRegularTestSetFromAdaptive(
    adaptiveTestSetId: string
  ): Promise<ExportAdaptiveTestSetResponse> {
    const encoded = encodeURIComponent(adaptiveTestSetId);
    return this.fetch<ExportAdaptiveTestSetResponse>(
      `${API_ENDPOINTS.adaptiveTesting}/export/${encoded}`,
      { method: 'POST' }
    );
  }

  async getAdaptiveSettings(testSetId: string): Promise<AdaptiveSettings> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<AdaptiveSettings>(`${basePath}/settings`, {
      cache: 'no-store',
    });
  }

  async updateAdaptiveSettings(
    testSetId: string,
    body: AdaptiveSettingsUpdateRequest
  ): Promise<AdaptiveSettings> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<AdaptiveSettings>(`${basePath}/settings`, {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  /**
   * Get the full adaptive testing tree for a test set.
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
   * Get a specific topic by path.
   * @param testSetId The test set identifier
   * @param topicPath The topic path (URL-encoded)
   */
  async getTopic(testSetId: string, topicPath: string): Promise<Topic> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<Topic>(`${basePath}/topics/${topicPath}`, {
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
  async deleteTopic(
    testSetId: string,
    topicPath: string
  ): Promise<DeleteTopicResponse> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<DeleteTopicResponse>(`${basePath}/topics/${topicPath}`, {
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
  async deleteTest(
    testSetId: string,
    testId: string
  ): Promise<DeleteTestResponse> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<DeleteTestResponse>(`${basePath}/tests/${testId}`, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Tree Operations
  // ===========================================================================

  /**
   * Validate the test tree structure.
   * @param testSetId The test set identifier
   */
  async validateTree(testSetId: string): Promise<TreeValidation> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TreeValidation>(`${basePath}/validate`, {
      cache: 'no-store',
    });
  }

  /**
   * Get statistics about the test tree.
   * @param testSetId The test set identifier
   */
  async getTreeStats(testSetId: string): Promise<TreeStats> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<TreeStats>(`${basePath}/stats`, {
      cache: 'no-store',
    });
  }

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
   * Generate test suggestions using an LLM.
   * @param testSetId The test set identifier
   * @param body Topic and generation parameters
   */
  async generateSuggestions(
    testSetId: string,
    body: GenerateSuggestionsRequest
  ): Promise<GenerateSuggestionsResponse> {
    const basePath = this.getBasePath(testSetId);
    return this.fetch<GenerateSuggestionsResponse>(
      `${basePath}/generate_suggestions`,
      {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  /**
   * Generate outputs for non-persisted suggestions by invoking an endpoint.
   * @param testSetId The test set identifier
   * @param body Endpoint ID and suggestion inputs
   */
  async generateSuggestionOutputsStream(
    testSetId: string,
    body: GenerateSuggestionOutputsRequest,
    handlers: {
      onEvent: (event: SuggestionOutputStreamEvent) => void;
    }
  ): Promise<void> {
    const basePath = this.getBasePath(testSetId);
    const url = joinUrl(
      this.baseUrl,
      `${basePath}/generate_suggestion_outputs`
    );
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
      // Defer to the existing error parsing by calling JSON fetch.
      // This will throw a rich Error with status/message.
      await this.fetch<GenerateSuggestionOutputsResponse>(
        `${basePath}/generate_suggestion_outputs`,
        {
          method: 'POST',
          body: JSON.stringify(body),
          headers: { 'Content-Type': 'application/json' },
        }
      );
      return;
    }

    for await (const event of this.readNdjsonStream(response)) {
      handlers.onEvent(event as SuggestionOutputStreamEvent);
    }
  }

  async generateSuggestionOutputs(
    testSetId: string,
    body: GenerateSuggestionOutputsRequest
  ): Promise<GenerateSuggestionOutputsResponse> {
    const results: GenerateSuggestionOutputsResponse['results'] = [];
    let generated = 0;

    await this.generateSuggestionOutputsStream(testSetId, body, {
      onEvent: event => {
        if (event.type === 'item') {
          results[event.index] = {
            input: event.input,
            output: event.output,
            error: event.error,
          };
        } else if (event.type === 'summary') {
          generated = event.generated;
        }
      },
    });

    return {
      generated,
      results: results.filter(Boolean),
    };
  }

  /**
   * Evaluate non-persisted suggestions with the specified metrics.
   * @param testSetId The test set identifier
   * @param body Metric names and suggestion input/output pairs
   */
  async evaluateSuggestions(
    testSetId: string,
    body: EvaluateSuggestionsRequest
  ): Promise<EvaluateSuggestionsResponse> {
    const results: EvaluateSuggestionsResponse['results'] = [];
    let evaluated = 0;

    await this.evaluateSuggestionsStream(testSetId, body, {
      onEvent: event => {
        if (event.type === 'item') {
          results[event.index] = {
            input: event.input,
            label: event.label,
            labeler: event.labeler,
            model_score: event.model_score,
            metrics: event.metrics,
            error: event.error,
          };
        } else if (event.type === 'summary') {
          evaluated = event.evaluated;
        }
      },
    });

    return {
      evaluated,
      results: results.filter(Boolean),
    };
  }

  async evaluateSuggestionsStream(
    testSetId: string,
    body: EvaluateSuggestionsRequest,
    handlers: {
      onEvent: (event: SuggestionEvalStreamEvent) => void;
    }
  ): Promise<void> {
    const basePath = this.getBasePath(testSetId);
    const url = joinUrl(this.baseUrl, `${basePath}/evaluate_suggestions`);
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
      await this.fetch<EvaluateSuggestionsResponse>(
        `${basePath}/evaluate_suggestions`,
        {
          method: 'POST',
          body: JSON.stringify(body),
          headers: { 'Content-Type': 'application/json' },
        }
      );
      return;
    }

    for await (const event of this.readNdjsonStream(response)) {
      handlers.onEvent(event as SuggestionEvalStreamEvent);
    }
  }

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
