import { BaseApiClient } from './base-client';
import {
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
} from './interfaces/adaptive-testing';

/**
 * API client for adaptive testing CRUD operations.
 *
 * Provides methods for managing test tree data within a TestSet,
 * including operations on topics and tests.
 */
export class AdaptiveTestingClient extends BaseApiClient {
  private getBasePath(testSetId: string): string {
    return `/adaptive-testing/${testSetId}`;
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
   * Delete a topic.
   * @param testSetId The test set identifier
   * @param topicPath The topic path to delete
   * @param moveTestsToParent Whether to move tests to parent (default: true)
   */
  async deleteTopic(
    testSetId: string,
    topicPath: string,
    moveTestsToParent: boolean = true
  ): Promise<DeleteTopicResponse> {
    const basePath = this.getBasePath(testSetId);
    const queryParams = `?move_tests_to_parent=${moveTestsToParent}`;
    return this.fetch<DeleteTopicResponse>(
      `${basePath}/topics/${topicPath}${queryParams}`,
      {
        method: 'DELETE',
      }
    );
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
}
