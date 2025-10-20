import { TestSetsClient } from './test-sets-client';
import { TokensClient } from './tokens-client';
import { ServicesClient } from './services-client';
import { EndpointsClient } from './endpoints-client';
import { OrganizationsClient } from './organizations-client';
import { TestsClient } from './tests-client';
import { UsersClient } from './users-client';
import { ProjectsClient } from './projects-client';
import { TestRunsClient } from './test-runs-client';
import { TestConfigurationsClient } from './test-configurations-client';
import { PromptsClient } from './prompts-client';
import { StatusClient } from './status-client';
import { BehaviorClient } from './behavior-client';
import { TopicClient } from './topic-client';
import { CategoryClient } from './category-client';
import { TypeLookupClient } from './type-lookup-client';
import { TestResultsClient } from './test-results-client';
import { MetricsClient } from './metrics-client';
import { ModelsClient } from './models-client';
import { TagsClient } from './tags-client';
import { CommentsClient } from './comments-client';
import { TasksClient } from './tasks-client';
import { SourcesClient } from './sources-client';
import { RecycleClient } from './recycle-client';

export class ApiClientFactory {
  private sessionToken: string;
  private metricsClient: MetricsClient | null = null;
  private modelsClient: ModelsClient | null = null;
  private tagsClient: TagsClient | null = null;
  private commentsClient: CommentsClient | null = null;
  private tasksClient: TasksClient | null = null;
  private sourcesClient: SourcesClient | null = null;
  private recycleClient: RecycleClient | null = null;

  constructor(sessionToken: string) {
    this.sessionToken = sessionToken;
  }

  getTestSetsClient(): TestSetsClient {
    return new TestSetsClient(this.sessionToken);
  }

  getTestsClient(): TestsClient {
    return new TestsClient(this.sessionToken);
  }

  getTokensClient(): TokensClient {
    return new TokensClient(this.sessionToken);
  }

  getServicesClient(): ServicesClient {
    return new ServicesClient(this.sessionToken);
  }

  getEndpointsClient(): EndpointsClient {
    return new EndpointsClient(this.sessionToken);
  }

  getOrganizationsClient(): OrganizationsClient {
    return new OrganizationsClient(this.sessionToken);
  }

  getUsersClient(): UsersClient {
    return new UsersClient(this.sessionToken);
  }

  getProjectsClient(): ProjectsClient {
    return new ProjectsClient(this.sessionToken);
  }

  getTestRunsClient(): TestRunsClient {
    return new TestRunsClient(this.sessionToken);
  }

  getTestConfigurationsClient(): TestConfigurationsClient {
    return new TestConfigurationsClient(this.sessionToken);
  }

  getPromptsClient(): PromptsClient {
    return new PromptsClient(this.sessionToken);
  }

  getStatusClient(): StatusClient {
    return new StatusClient(this.sessionToken);
  }

  getBehaviorClient(): BehaviorClient {
    return new BehaviorClient(this.sessionToken);
  }

  getTopicClient(): TopicClient {
    return new TopicClient(this.sessionToken);
  }

  getCategoryClient(): CategoryClient {
    return new CategoryClient(this.sessionToken);
  }

  getTypeLookupClient(): TypeLookupClient {
    return new TypeLookupClient(this.sessionToken);
  }

  getTestResultsClient(): TestResultsClient {
    return new TestResultsClient(this.sessionToken);
  }

  getMetricsClient(): MetricsClient {
    if (!this.metricsClient) {
      this.metricsClient = new MetricsClient(this.sessionToken);
    }
    return this.metricsClient;
  }

  getModelsClient(): ModelsClient {
    if (!this.modelsClient) {
      this.modelsClient = new ModelsClient(this.sessionToken);
    }
    return this.modelsClient;
  }

  getTagsClient(): TagsClient {
    if (!this.tagsClient) {
      this.tagsClient = new TagsClient(this.sessionToken);
    }
    return this.tagsClient;
  }

  getCommentsClient(): CommentsClient {
    if (!this.commentsClient) {
      this.commentsClient = new CommentsClient(this.sessionToken);
    }
    return this.commentsClient;
  }

  getTasksClient(): TasksClient {
    if (!this.tasksClient) {
      this.tasksClient = new TasksClient(this.sessionToken);
    }
    return this.tasksClient;
  }

  getSourcesClient(): SourcesClient {
    if (!this.sourcesClient) {
      this.sourcesClient = new SourcesClient(this.sessionToken);
    }
    return this.sourcesClient;
  }

  getRecycleClient(): RecycleClient {
    if (!this.recycleClient) {
      this.recycleClient = new RecycleClient(this.sessionToken);
    }
    return this.recycleClient;
  }
}
