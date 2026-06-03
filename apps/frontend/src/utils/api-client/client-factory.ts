import { ExplorerClient } from './explorer-client';
import { ArchitectClient } from './architect-client';
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
import { ToolsClient } from './tools-client';
import { TelemetryClient } from './telemetry-client';
import { GarakClient } from './garak-client';
import { ImportClient } from './import-client';
import { FilesClient } from './files-client';
import { FeaturesClient } from './features-client';
import { ParametersClient } from './parameters-client';
import { PreflightClient } from './preflight-client';

export class ApiClientFactory {
  private sessionToken: string;
  private projectId?: string;
  private explorerClient: ExplorerClient | null = null;
  private metricsClient: MetricsClient | null = null;
  private modelsClient: ModelsClient | null = null;
  private tagsClient: TagsClient | null = null;
  private commentsClient: CommentsClient | null = null;
  private tasksClient: TasksClient | null = null;
  private sourcesClient: SourcesClient | null = null;
  private recycleClient: RecycleClient | null = null;
  private toolsClient: ToolsClient | null = null;
  private telemetryClient: TelemetryClient | null = null;
  private garakClient: GarakClient | null = null;
  private importClient: ImportClient | null = null;
  private filesClient: FilesClient | null = null;
  private featuresClient: FeaturesClient | null = null;
  private architectClient: ArchitectClient | null = null;
  private parametersClient: ParametersClient | null = null;
  private preflightClient: PreflightClient | null = null;

  /**
   * @param sessionToken The user's session token.
   * @param projectId Optional active project id. Pass this on the server (where the
   *   `rh_active_project_id` cookie is not readable via `document.cookie`) so that
   *   server-rendered fetches carry the `X-Project-Id` scope. On the client it can be
   *   omitted — the clients fall back to the cookie.
   */
  constructor(sessionToken: string, projectId?: string) {
    this.sessionToken = sessionToken;
    this.projectId = projectId;
  }

  getExplorerClient(): ExplorerClient {
    if (!this.explorerClient) {
      this.explorerClient = new ExplorerClient(
        this.sessionToken,
        undefined,
        this.projectId
      );
    }
    return this.explorerClient;
  }

  getTestSetsClient(): TestSetsClient {
    return new TestSetsClient(this.sessionToken, undefined, this.projectId);
  }

  getTestsClient(): TestsClient {
    return new TestsClient(this.sessionToken, undefined, this.projectId);
  }

  getTokensClient(): TokensClient {
    return new TokensClient(this.sessionToken, undefined, this.projectId);
  }

  getServicesClient(): ServicesClient {
    return new ServicesClient(this.sessionToken, undefined, this.projectId);
  }

  getEndpointsClient(): EndpointsClient {
    return new EndpointsClient(this.sessionToken, undefined, this.projectId);
  }

  getOrganizationsClient(): OrganizationsClient {
    return new OrganizationsClient(this.sessionToken, undefined, this.projectId);
  }

  getUsersClient(): UsersClient {
    return new UsersClient(this.sessionToken, undefined, this.projectId);
  }

  getProjectsClient(): ProjectsClient {
    return new ProjectsClient(this.sessionToken, undefined, this.projectId);
  }

  getTestRunsClient(): TestRunsClient {
    return new TestRunsClient(this.sessionToken, undefined, this.projectId);
  }

  getTestConfigurationsClient(): TestConfigurationsClient {
    return new TestConfigurationsClient(this.sessionToken, undefined, this.projectId);
  }

  getPromptsClient(): PromptsClient {
    return new PromptsClient(this.sessionToken, undefined, this.projectId);
  }

  getStatusClient(): StatusClient {
    return new StatusClient(this.sessionToken, undefined, this.projectId);
  }

  getBehaviorClient(): BehaviorClient {
    return new BehaviorClient(this.sessionToken, undefined, this.projectId);
  }

  getTopicClient(): TopicClient {
    return new TopicClient(this.sessionToken, undefined, this.projectId);
  }

  getCategoryClient(): CategoryClient {
    return new CategoryClient(this.sessionToken, undefined, this.projectId);
  }

  getTypeLookupClient(): TypeLookupClient {
    return new TypeLookupClient(this.sessionToken, undefined, this.projectId);
  }

  getTestResultsClient(): TestResultsClient {
    return new TestResultsClient(this.sessionToken, undefined, this.projectId);
  }

  getMetricsClient(): MetricsClient {
    if (!this.metricsClient) {
      this.metricsClient = new MetricsClient(this.sessionToken, undefined, this.projectId);
    }
    return this.metricsClient;
  }

  getModelsClient(): ModelsClient {
    if (!this.modelsClient) {
      this.modelsClient = new ModelsClient(this.sessionToken, undefined, this.projectId);
    }
    return this.modelsClient;
  }

  getTagsClient(): TagsClient {
    if (!this.tagsClient) {
      this.tagsClient = new TagsClient(this.sessionToken, undefined, this.projectId);
    }
    return this.tagsClient;
  }

  getCommentsClient(): CommentsClient {
    if (!this.commentsClient) {
      this.commentsClient = new CommentsClient(this.sessionToken, undefined, this.projectId);
    }
    return this.commentsClient;
  }

  getTasksClient(): TasksClient {
    if (!this.tasksClient) {
      this.tasksClient = new TasksClient(this.sessionToken, undefined, this.projectId);
    }
    return this.tasksClient;
  }

  getSourcesClient(): SourcesClient {
    if (!this.sourcesClient) {
      this.sourcesClient = new SourcesClient(this.sessionToken, undefined, this.projectId);
    }
    return this.sourcesClient;
  }

  getRecycleClient(): RecycleClient {
    if (!this.recycleClient) {
      this.recycleClient = new RecycleClient(this.sessionToken, undefined, this.projectId);
    }
    return this.recycleClient;
  }

  getToolsClient(): ToolsClient {
    if (!this.toolsClient) {
      this.toolsClient = new ToolsClient(this.sessionToken, undefined, this.projectId);
    }
    return this.toolsClient;
  }

  getTelemetryClient(): TelemetryClient {
    if (!this.telemetryClient) {
      this.telemetryClient = new TelemetryClient(this.sessionToken, undefined, this.projectId);
    }
    return this.telemetryClient;
  }

  getGarakClient(): GarakClient {
    if (!this.garakClient) {
      this.garakClient = new GarakClient(this.sessionToken, undefined, this.projectId);
    }
    return this.garakClient;
  }

  getImportClient(): ImportClient {
    if (!this.importClient) {
      this.importClient = new ImportClient(this.sessionToken, undefined, this.projectId);
    }
    return this.importClient;
  }

  getFilesClient(): FilesClient {
    if (!this.filesClient) {
      this.filesClient = new FilesClient(this.sessionToken, undefined, this.projectId);
    }
    return this.filesClient;
  }

  getFeaturesClient(): FeaturesClient {
    if (!this.featuresClient) {
      this.featuresClient = new FeaturesClient(this.sessionToken, undefined, this.projectId);
    }
    return this.featuresClient;
  }

  getArchitectClient(): ArchitectClient {
    if (!this.architectClient) {
      this.architectClient = new ArchitectClient(this.sessionToken, undefined, this.projectId);
    }
    return this.architectClient;
  }

  getParametersClient(): ParametersClient {
    if (!this.parametersClient) {
      this.parametersClient = new ParametersClient(this.sessionToken, undefined, this.projectId);
    }
    return this.parametersClient;
  }

  getPreflightClient(): PreflightClient {
    if (!this.preflightClient) {
      this.preflightClient = new PreflightClient(this.sessionToken, undefined, this.projectId);
    }
    return this.preflightClient;
  }
}
