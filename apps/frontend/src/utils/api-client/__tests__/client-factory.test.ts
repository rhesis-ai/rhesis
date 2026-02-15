import { ApiClientFactory } from '../client-factory';
import { MetricsClient } from '../metrics-client';
import { ModelsClient } from '../models-client';
import { TagsClient } from '../tags-client';
import { CommentsClient } from '../comments-client';
import { TasksClient } from '../tasks-client';
import { TestsClient } from '../tests-client';
import { ProjectsClient } from '../projects-client';
import { TestRunsClient } from '../test-runs-client';

// Mock all the client classes
jest.mock('../metrics-client');
jest.mock('../models-client');
jest.mock('../tags-client');
jest.mock('../comments-client');
jest.mock('../tasks-client');
jest.mock('../tests-client');
jest.mock('../projects-client');
jest.mock('../test-runs-client');
jest.mock('../organizations-client');
jest.mock('../users-client');
jest.mock('../tokens-client');
jest.mock('../services-client');
jest.mock('../endpoints-client');
jest.mock('../test-sets-client');
jest.mock('../test-configurations-client');
jest.mock('../prompts-client');
jest.mock('../status-client');
jest.mock('../behavior-client');
jest.mock('../topic-client');
jest.mock('../category-client');
jest.mock('../type-lookup-client');
jest.mock('../test-results-client');

describe('ApiClientFactory', () => {
  const mockSessionToken = 'mock-session-token';

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    it('initializes with session token', () => {
      const factory = new ApiClientFactory(mockSessionToken);
      expect(factory).toBeInstanceOf(ApiClientFactory);
    });
  });

  describe('client creation', () => {
    it('creates instances of required clients', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      // Test clients that should be created immediately
      factory.getTestsClient();
      factory.getProjectsClient();
      factory.getTestRunsClient();

      expect(TestsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(ProjectsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(TestRunsClient).toHaveBeenCalledWith(mockSessionToken);
    });

    it('creates singleton instances for cached clients', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      // First call
      const metricsClient1 = factory.getMetricsClient();
      expect(MetricsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(MetricsClient).toHaveBeenCalledTimes(1);

      // Second call should return the same instance (singleton behavior)
      const metricsClient2 = factory.getMetricsClient();
      expect(MetricsClient).toHaveBeenCalledTimes(1); // Still only called once
      expect(metricsClient1).toBe(metricsClient2);
    });

    it('creates separate instances for non-cached clients', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      // Call getTestsClient twice
      const testsClient1 = factory.getTestsClient();
      const testsClient2 = factory.getTestsClient();

      expect(TestsClient).toHaveBeenCalledTimes(2);
      // For non-cached clients, they should be different instances
      expect(testsClient1).not.toBe(testsClient2);
    });

    it('passes correct session token to all clients', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      // Test a variety of clients
      factory.getMetricsClient();
      factory.getModelsClient();
      factory.getTagsClient();
      factory.getCommentsClient();
      factory.getTasksClient();

      expect(MetricsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(ModelsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(TagsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(CommentsClient).toHaveBeenCalledWith(mockSessionToken);
      expect(TasksClient).toHaveBeenCalledWith(mockSessionToken);
    });

    it('handles multiple factory instances with different tokens', () => {
      const token1 = 'token-1';
      const token2 = 'token-2';

      const factory1 = new ApiClientFactory(token1);
      const factory2 = new ApiClientFactory(token2);

      factory1.getTestsClient();
      factory2.getTestsClient();

      expect(TestsClient).toHaveBeenCalledWith(token1);
      expect(TestsClient).toHaveBeenCalledWith(token2);
      expect(TestsClient).toHaveBeenCalledTimes(2);
    });
  });

  describe('cached clients', () => {
    it('caches MetricsClient instance', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      factory.getMetricsClient();
      factory.getMetricsClient();
      factory.getMetricsClient();

      expect(MetricsClient).toHaveBeenCalledTimes(1);
    });

    it('caches ModelsClient instance', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      factory.getModelsClient();
      factory.getModelsClient();
      factory.getModelsClient();

      expect(ModelsClient).toHaveBeenCalledTimes(1);
    });

    it('caches TagsClient instance', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      factory.getTagsClient();
      factory.getTagsClient();
      factory.getTagsClient();

      expect(TagsClient).toHaveBeenCalledTimes(1);
    });

    it('caches CommentsClient instance', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      factory.getCommentsClient();
      factory.getCommentsClient();
      factory.getCommentsClient();

      expect(CommentsClient).toHaveBeenCalledTimes(1);
    });

    it('caches TasksClient instance', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      factory.getTasksClient();
      factory.getTasksClient();
      factory.getTasksClient();

      expect(TasksClient).toHaveBeenCalledTimes(1);
    });
  });

  describe('all client getters', () => {
    it('provides access to all available clients', () => {
      const factory = new ApiClientFactory(mockSessionToken);

      // Verify all getter methods exist and can be called
      expect(typeof factory.getTestSetsClient).toBe('function');
      expect(typeof factory.getTestsClient).toBe('function');
      expect(typeof factory.getTokensClient).toBe('function');
      expect(typeof factory.getServicesClient).toBe('function');
      expect(typeof factory.getEndpointsClient).toBe('function');
      expect(typeof factory.getOrganizationsClient).toBe('function');
      expect(typeof factory.getUsersClient).toBe('function');
      expect(typeof factory.getProjectsClient).toBe('function');
      expect(typeof factory.getTestRunsClient).toBe('function');
      expect(typeof factory.getTestConfigurationsClient).toBe('function');
      expect(typeof factory.getPromptsClient).toBe('function');
      expect(typeof factory.getStatusClient).toBe('function');
      expect(typeof factory.getBehaviorClient).toBe('function');
      expect(typeof factory.getTopicClient).toBe('function');
      expect(typeof factory.getCategoryClient).toBe('function');
      expect(typeof factory.getTypeLookupClient).toBe('function');
      expect(typeof factory.getTestResultsClient).toBe('function');
      expect(typeof factory.getMetricsClient).toBe('function');
      expect(typeof factory.getModelsClient).toBe('function');
      expect(typeof factory.getTagsClient).toBe('function');
      expect(typeof factory.getCommentsClient).toBe('function');
      expect(typeof factory.getTasksClient).toBe('function');
    });
  });
});
