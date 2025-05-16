declare module '@/utils/api-client/interfaces/project' {
  import { User } from '@/utils/api-client/interfaces/user'; // Assume User exists
  import { UUID } from 'crypto';

  export type ProjectEnvironment = 'development' | 'staging' | 'production';
  export type ProjectUseCase = 'chatbot' | 'assistant' | 'advisor' | 'other';
  export type SortOrder = 'asc' | 'desc';

  export interface ProjectBase {
    name: string;
    description?: string;
    is_active?: boolean;
    user_id?: UUID | string;
    owner_id?: UUID | string;
    organization_id?: UUID | string;
  }

  export interface ProjectsQueryParams {
    skip?: number;
    limit?: number;
    sort_by?: string;
    sort_order?: SortOrder;
    $filter?: string | (string | null);
  }

  export interface ProjectCreate extends ProjectBase {
    icon?: string;
  }

  export interface ProjectUpdate extends Partial<ProjectBase> {}

  export interface ProjectUser {
    id: UUID | string;
    name: string;
    email: string;
    family_name: string;
    given_name: string;
    picture: string;
    organization_id: UUID | string;
  }

  export interface ProjectOrganization {
    id: UUID | string;
    name: string;
    description: string;
    email: string;
    user_id: UUID | string;
  }

  export interface ProjectSystem {
    name: string;
    description: string;
    primary_goals: string[];
    key_capabilities: string[];
  }

  export interface ProjectAgent {
    name: string;
    description: string;
    responsibilities: string[];
  }

  export interface ProjectEntity {
    name: string;
    description: string;
  }

  export interface ProjectFrontendFields {
    environment?: ProjectEnvironment | string;
    useCase?: ProjectUseCase | string;
    icon?: string;
    tags?: string[];
    createdAt?: string;
    system?: ProjectSystem;
    agents?: ProjectAgent[];
    requirements?: ProjectEntity[];
    scenarios?: ProjectEntity[];
    personas?: ProjectEntity[];
  }

  export interface Project extends ProjectBase, ProjectFrontendFields {
    id: UUID | string;
    created_at?: string;
    updated_at?: string;
    user: ProjectUser;
    owner: ProjectUser;
    organization: ProjectOrganization;
  }
}

declare module '@/utils/api-client/interfaces/user' {
  import { UUID } from 'crypto';

  export interface User {
    id: UUID;
    email: string;
    name?: string;
    given_name?: string;
    family_name?: string;
    auth0_id?: string;
    picture?: string;
    is_active?: boolean;
    organization_id?: UUID;
  }

  export interface UserCreate {
    email: string;
    name?: string;
    given_name?: string;
    family_name?: string;
    auth0_id?: string;
    picture?: string;
    is_active?: boolean;
    organization_id?: UUID;
  }

  export interface UserUpdate {
    email?: string;
    name?: string;
    given_name?: string;
    family_name?: string;
    auth0_id?: string;
    picture?: string;
    is_active?: boolean;
    organization_id?: UUID;
  }
}

declare module '@/utils/api-client/interfaces/test-results' {
  import { UUID } from 'crypto';
  import { UserReference, Organization, Status, TestTag } from '@/utils/api-client/interfaces/tests';

  export interface MetricResult {
    score: number;
    reason: string;
    backend: string;
    threshold: number;
    description: string;
    is_successful: boolean;
  }

  export interface TestMetrics {
    metrics: {
      [key: string]: MetricResult;
    };
    execution_time: number;
  }

  export interface TestOutput {
    output: string;
    context: string[];
    session_id: string;
  }

  export interface TestResultBase {
    test_configuration_id: UUID;
    test_run_id?: UUID;
    prompt_id?: UUID;
    test_id?: UUID;
    status_id?: UUID;
    test_metrics?: TestMetrics;
    test_output?: TestOutput;
    user_id?: UUID;
    organization_id?: UUID;
  }

  export interface TestResultCreate extends TestResultBase {}

  export interface TestResultUpdate extends Partial<TestResultBase> {}

  export interface TestResult extends TestResultBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }

  export interface TestResultDetail extends TestResult {
    user?: UserReference;
    organization?: Organization;
    status?: Status;
    test_configuration?: TestConfiguration;
    test_run?: TestRun;
    test?: TestReference;
  }

  export interface TestResultStatsDimensionBreakdown {
    dimension: string;
    total: number;
    breakdown: Record<string, number>;
  }

  export interface TestResultStatsHistorical {
    period: string;
    start_date: string;
    end_date: string;
    monthly_counts: Record<string, number>;
  }

  export interface TestResultStats {
    total: number;
    stats: {
      user: TestResultStatsDimensionBreakdown;
      status: TestResultStatsDimensionBreakdown;
      organization: TestResultStatsDimensionBreakdown;
      [key: string]: TestResultStatsDimensionBreakdown;
    };
    metadata: {
      generated_at: string;
      organization_id: UUID;
      entity_type: string;
    };
    history?: TestResultStatsHistorical;
  }
}

declare module '@/utils/api-client/interfaces/pagination' {
  export interface PaginationParams {
    /** Number of items to skip (offset) */
    skip: number;
    /** Maximum number of items to return */
    limit: number;
    /** Field to sort by */
    sortBy?: string;
    /** Sort order ('asc' or 'desc') */
    sortOrder?: 'asc' | 'desc';
  }

  export interface PaginationMetadata {
    /** Total number of items available */
    totalCount: number;
    /** Current page number (0-based) */
    currentPage: number;
    /** Number of items per page */
    pageSize: number;
    /** Total number of pages available */
    totalPages: number;
  }

  export interface PaginatedResponse<T> {
    /** Array of items for the current page */
    data: T[];
    /** Pagination metadata */
    pagination: {
      totalCount: number;
      skip: number;
      limit: number;
      currentPage: number;
      pageSize: number;
      totalPages: number;
    };
  }
}

declare module '@/utils/api-client/interfaces/prompt' {
  import { UUID } from 'crypto';

  export interface Tag {
    id: UUID;
    name: string;
    icon_unicode?: string;
    organization_id?: UUID;
  }

  export interface PromptBase {
    content: string;
    demographic_id?: UUID;
    category_id?: UUID;
    attack_category_id?: UUID;
    topic_id?: UUID;
    language_code: string;
    behavior_id?: UUID;
    parent_id?: UUID;
    prompt_template_id?: UUID;
    expected_response?: string;
    source_id?: UUID;
    user_id?: UUID;
    organization_id?: UUID;
    status_id?: UUID;
    tags?: Tag[];
  }

  export interface PromptCreate extends PromptBase {}

  export interface PromptUpdate extends Partial<PromptBase> {}

  export interface Prompt extends PromptBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }
}

// Assuming Test interface is defined correctly elsewhere or define basic structure
declare module '@/utils/api-client/interfaces/tests' {
  import { UUID } from 'crypto';
  import { Prompt } from '@/utils/api-client/interfaces/prompt';

  export interface TestBulkCreateRequest {
    tests: Array<{
      prompt: { content: string; language_code: string };
      behavior: string;
      category: string;
      topic: string;
      test_configuration: Record<string, any>;
      priority: number;
      assignee_id?: UUID;
      owner_id?: UUID;
      status?: string;
    }>;
  }

  export type PriorityLevel = 'Low' | 'Medium' | 'High' | 'Urgent';

  export interface UserReference {
    id: UUID;
    name?: string;
    given_name?: string;
    family_name?: string;
    email?: string;
    picture?: string;
  }

  export interface TypeLookup {
    id: UUID;
    type_name: string;
    type_value: string;
    description?: string;
  }

  export interface Topic {
    id: UUID;
    name: string;
    description?: string;
  }

  export interface Status {
    id: UUID;
    name: string;
    description?: string;
  }

  export interface Behavior {
    id: UUID;
    name: string;
    description?: string;
  }

  export interface Category {
    id: UUID;
    name: string;
    description?: string;
  }

  export interface Organization {
    id: UUID;
    name: string;
    description?: string;
    email?: string;
  }

  export interface TestTag {
    id: UUID;
    name: string;
    icon_unicode?: string;
  }

  export interface TestBase {
    prompt_id: UUID;
    test_type_id?: UUID;
    priority?: number;
    user_id?: UUID;
    assignee_id?: UUID;
    owner_id?: UUID;
    test_configuration?: Record<string, any>;
    parent_id?: UUID;
    topic_id?: UUID;
    behavior_id?: UUID;
    category_id?: UUID;
    status_id?: UUID;
    organization_id?: UUID;
    tags?: TestTag[];
  }

  export interface TestCreate extends TestBase {}

  export interface TestUpdate extends Partial<TestBase> {}

  export interface Test extends TestBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }

  export interface TestDetail extends Test {
    prompt?: Prompt;
    test_type?: TypeLookup;
    user?: UserReference;
    assignee?: UserReference;
    owner?: UserReference;
    parent?: TestDetail;
    topic?: Topic;
    behavior?: Behavior;
    category?: Category;
    status?: Status;
    organization?: Organization;
    priorityLevel?: PriorityLevel;
  }

  export interface TestStatsDimensionBreakdown {
    dimension: string;
    total: number;
    breakdown: Record<string, number>;
  }

  export interface TestStatsHistorical {
    period: string;
    start_date: string;
    end_date: string;
    monthly_counts: Record<string, number>;
  }

  export interface TestStats {
    total: number;
    stats: {
      user: TestStatsDimensionBreakdown;
      assignee: TestStatsDimensionBreakdown;
      owner: TestStatsDimensionBreakdown;
      topic: TestStatsDimensionBreakdown;
      behavior: TestStatsDimensionBreakdown;
      category: TestStatsDimensionBreakdown;
      status: TestStatsDimensionBreakdown;
      organization: TestStatsDimensionBreakdown;
      priority: TestStatsDimensionBreakdown;
      [key: string]: TestStatsDimensionBreakdown;
    };
    metadata: {
      generated_at: string;
      organization_id: UUID;
      entity_type: string;
    };
    history?: TestStatsHistorical;
  }
}

declare module '@/utils/api-client/interfaces/test-configuration' {
  import { UUID } from 'crypto';
  import { UserReference, TypeLookup, Topic, Status, Category } from '@/utils/api-client/interfaces/tests';
  import { Prompt } from '@/utils/api-client/interfaces/prompt';
  import { TestSet } from '@/utils/api-client/interfaces/test-set';
  import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

  export interface TestConfigurationBase {
    endpoint_id: UUID;
    category_id?: UUID;
    topic_id?: UUID;
    prompt_id?: UUID;
    use_case_id?: UUID;
    test_set_id: UUID;
    user_id: UUID;
    organization_id?: UUID;
    status_id?: UUID;
  }

  export interface TestConfigurationCreate extends TestConfigurationBase {}

  export interface TestConfigurationUpdate extends Partial<TestConfigurationBase> {}

  export interface TestConfiguration extends TestConfigurationBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }

  export interface UseCase {
    id: UUID;
    name: string;
    description?: string;
  }

  export interface TestConfigurationDetail extends TestConfiguration {
    endpoint?: Endpoint;
    category?: Category;
    topic?: Topic;
    prompt?: Prompt;
    use_case?: UseCase;
    test_set?: TestSet;
    user?: UserReference;
    status?: Status;
  }

  export interface TestConfigurationExecuteResponse {
    test_configuration_id: string;
    task_id: string;
    status: string;
    endpoint_id: string;
    test_set_id: string;
    user_id: string;
  }
}

declare module '@/utils/api-client/client-factory' {
  import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
  import { Project } from '@/utils/api-client/interfaces/project';
  import { Prompt } from '@/utils/api-client/interfaces/prompt';
  import { TestDetail } from '@/utils/api-client/interfaces/tests';
  import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
  import { PaginationParams, PaginatedResponse } from '@/utils/api-client/interfaces/pagination';
  import { User } from '@/utils/api-client/interfaces/user'; // Import User
  import { Status } from '@/utils/api-client/interfaces/status';
  import { TestSet } from '@/utils/api-client/interfaces/test-set';
  import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
  import { OrganizationCreate } from '@/utils/api-client/organizations-client';
  import { UserUpdate } from '@/utils/api-client/interfaces/user';
  import { Metric, CreateMetricRequest, UpdateMetricRequest } from '@/utils/api-client/interfaces/metrics';
  import { Model, ModelCreate, ModelUpdate } from './interfaces/model';

  // Define placeholder types for the clients
  interface TestsClient {
    getTest(id: string): Promise<TestDetail>;
    getTests(params: Partial<PaginationParams>): Promise<PaginatedResponse<TestDetail>>;
    getTestStats(params: { top: number; months: number }): Promise<TestStats>;
    updateTest(id: string, data: Partial<TestDetail>): Promise<TestDetail>;
    createTestsBulk(data: TestBulkCreateRequest): Promise<{ success: boolean; message?: string }>;
  }
  interface PromptsClient {
    getPrompt(id: string): Promise<Prompt>; // Use defined Prompt
    updatePrompt(id: string, data: Partial<Prompt>): Promise<Prompt>; // Use defined Prompt
    // Add other PromptsClient methods as needed
  }

  // Define TestSetsClient interface based on usage
  interface TestSetsClient {
    getTestSets(params: Partial<PaginationParams> & { $filter?: string }): Promise<PaginatedResponse<TestSet>>;
    executeTestSet(testSetId: string, endpointId: string): Promise<any>;
    getTestSetDetailStats(testSetId: string, params: { top: number; months: number; mode: string }): Promise<any>;
    getTestSetTests(testSetId: string, params: Partial<PaginationParams>): Promise<PaginatedResponse<TestDetail>>;
    disassociateTestsFromTestSet(testSetId: string, testIds: string[]): Promise<void>;
    updateTestSet(testSetId: string, data: Partial<TestSet>): Promise<TestSet>;
    createTestSet(data: Partial<TestSet>): Promise<TestSet>;
    getTestSetStats(params: { top: number; months: number; mode: string }): Promise<any>;
  }
  
  // Define basic TestRun type for getTestRun response
  interface TestRun {
      id: string;
      name?: string;
      status?: { name?: string };
      assignee?: User;
      owner?: User;
      test_configuration_id?: string;
      created_at: string;
      updated_at: string;
  }

  // Define TestRunsClient interface
  interface TestRunsClient {
    getTestRun(testRunId: string): Promise<TestRunDetail>;
    getTestRuns(params?: Partial<PaginationParams>): Promise<PaginatedResponse<TestRunDetail>>;
    createTestRun(data: TestRunCreate): Promise<TestRun>;
    updateTestRun(testRunId: string, data: Partial<TestRunDetail>): Promise<TestRunDetail>;
    deleteTestRun(id: string): Promise<void>;
    getTestRunsByTestConfiguration(testConfigurationId: string, params?: Partial<PaginationParams>): Promise<PaginatedResponse<TestRunDetail>>;
  }

  // Define TestConfigurationsClient interface
  interface TestConfigurationsClient {
    executeTestConfiguration(testConfigurationId: string): Promise<any>;
    createTestConfiguration(data: TestConfigurationCreate): Promise<TestConfiguration>;
    getTestConfiguration(id: string): Promise<TestConfigurationDetail>;
    getTestConfigurations(params?: Partial<PaginationParams>): Promise<PaginatedResponse<TestConfigurationDetail>>;
    updateTestConfiguration(id: string, data: TestConfigurationUpdate): Promise<TestConfiguration>;
    deleteTestConfiguration(id: string): Promise<TestConfiguration>;
    getTestRunsByTestConfiguration(id: string, params?: Partial<PaginationParams>): Promise<PaginatedResponse<TestRunDetail>>;
    getLatestTestRun(id: string): Promise<TestRunDetail | null>;
  }

  // Define TestResultsClient interface
  interface TestResultsClient {
    getTestResults(params: Partial<PaginationParams> & { filter: string }): Promise<PaginatedResponse<TestResultDetail>>; // Use defined TestResultDetail and allow partial PaginationParams
  }

  // Add StatusClient interface
  interface StatusClient {
    getStatus(id: string): Promise<Status>;
    getStatuses(params?: { entity_type?: string; sort_by?: string; sort_order?: string }): Promise<Status[]>;
  }

  // Add UsersClient interface
  interface UsersClient {
    getUser(id: string): Promise<User>;
    getUsers(params?: Partial<PaginationParams>): Promise<User[]>;
    updateUser(id: string, data: UserUpdate): Promise<{ session_token: string }>;
  }

  // Add OrganizationsClient interface
  interface OrganizationsClient {
    createOrganization(data: OrganizationCreate): Promise<{ id: string }>;
    loadInitialData(organizationId: string): Promise<{ status: string }>;
  }

  // Update EndpointsClient interface
  interface EndpointsClient {
    getEndpoints(params?: Partial<PaginationParams>): Promise<PaginatedResponse<Endpoint>>;
    createEndpoint(data: Omit<Endpoint, 'id'>): Promise<Endpoint>;
    updateEndpoint(id: string, data: Partial<Endpoint>): Promise<Endpoint>;
    invokeEndpoint(id: string, inputData: any): Promise<any>;
    getEndpoint(id: string): Promise<Endpoint>;
    executeEndpoint(id: string, test_set_ids: string[]): Promise<any>;
  }

  // Define BehaviorClient interface
  interface BehaviorClient {
    getBehaviors(params?: { sort_by?: string; sort_order?: string }): Promise<Behavior[]>;
    getBehavior(id: string): Promise<Behavior>;
    createBehavior(data: { name: string }): Promise<Behavior>;
    updateBehavior(id: string, data: Partial<Behavior>): Promise<Behavior>;
  }

  // Define TopicClient interface
  interface TopicClient {
    getTopics(params?: { entity_type?: string; sort_by?: string; sort_order?: string }): Promise<any[]>;
    createTopic(data: { name: string }): Promise<{ id: UUID; name: string }>;
  }

  // Define CategoryClient interface
  interface CategoryClient {
    getCategories(params?: { entity_type?: string; sort_by?: string; sort_order?: string }): Promise<any[]>;
    createCategory(data: { name: string }): Promise<{ id: UUID; name: string }>;
  }

  // Define TypeLookupClient interface
  interface TypeLookupClient {
    getTypeLookups(params?: { sort_by?: string; sort_order?: string; $filter?: string }): Promise<any[]>;
  }

  // Define TokensClient interface
  interface TokensClient {
    listTokens(params: Partial<PaginationParams>): Promise<PaginatedResponse<Token>>;
    createToken(name: string, expiresInDays: number | null): Promise<TokenResponse>;
    refreshToken(tokenId: string, expiresInDays: number | null): Promise<TokenResponse>;
    deleteToken(tokenId: string): Promise<void>;
  }

  interface MetricsClient {
    getMetrics(params?: { status?: string; type?: string; sort_by?: string; sort_order?: string }): Promise<Metric[]>;
    getMetric(id: string): Promise<Metric>;
    createMetric(data: CreateMetricRequest): Promise<Metric>;
    updateMetric(id: string, data: UpdateMetricRequest): Promise<Metric>;
    deleteMetric(id: string): Promise<void>;
  }

  interface ServicesClient {
    getGitHubContents(repo_url: string): Promise<string>;
    getOpenAIJson(prompt: string): Promise<any>;
    getOpenAIChat(messages: Array<{ role: string; content: string }>): Promise<string>;
  }

  interface ProjectsClient {
    getProjects(params?: Partial<PaginationParams>): Promise<PaginatedResponse<Project>>;
    getProject(id: string): Promise<Project>;
    updateProject(id: string, data: Partial<Project>): Promise<Project>;
    deleteProject(id: string): Promise<void>;
    createProject(data: ProjectCreate): Promise<Project>;
  }

  export interface ModelsClient {
    getModels(params?: any): Promise<PaginatedResponse<Model>>;
    getModel(id: string): Promise<Model>;
    createModel(model: ModelCreate): Promise<Model>;
    updateModel(id: string, model: ModelUpdate): Promise<Model>;
    deleteModel(id: string): Promise<void>;
  }

  export class ApiClientFactory {
    constructor(sessionToken: string);
    getEndpointsClient(): EndpointsClient;
    getProjectsClient(): ProjectsClient;
    getTestsClient(): TestsClient;
    getPromptsClient(): PromptsClient;
    getTestSetsClient(): TestSetsClient;
    getTestRunsClient(): TestRunsClient;
    getTestConfigurationsClient(): TestConfigurationsClient;
    getTestResultsClient(): TestResultsClient;
    getStatusClient(): StatusClient;
    getUsersClient(): UsersClient;
    getOrganizationsClient(): OrganizationsClient;
    getBehaviorClient(): BehaviorClient;
    getTopicClient(): TopicClient;
    getCategoryClient(): CategoryClient;
    getTypeLookupClient(): TypeLookupClient;
    getTokensClient(): TokensClient;
    getServicesClient(): ServicesClient;
    getMetricsClient(): MetricsClient;
    getModelsClient(): ModelsClient;
  }
}

declare module '@/auth' {
  import { UUID } from 'crypto';

  export interface Session {
    session_token?: string;
    user?: {
      id: UUID;
      email?: string;
      name?: string;
      picture?: string;
    };
  }
  
  export function auth(): Promise<Session | null>;
  export function signIn(provider: string, options?: any): Promise<any>;
  export function signOut(options?: any): Promise<any>;
}

declare module '@/utils/api-client/interfaces/endpoint' {
  import { UUID } from 'crypto';

  export interface Endpoint {
    id: string;
    name: string;
    description?: string;
    protocol: 'REST' | 'WEBSOCKET' | 'GRPC';
    url: string;
    auth?: Record<string, any>;
    environment: 'development' | 'staging' | 'production';
    config_source: 'manual' | 'openapi' | 'llm_generated';
    openapi_spec_url?: string;
    openapi_spec?: Record<string, any>;
    llm_suggestions?: Record<string, any>;
    method?: string;
    endpoint_path?: string;
    request_headers?: Record<string, string>;
    query_params?: Record<string, any>;
    request_body_template?: Record<string, any>;
    input_mappings?: Record<string, any>;
    response_format: 'json' | 'xml' | 'text';
    response_mappings?: Record<string, string>;
    validation_rules?: Record<string, any>;
    status_id?: string;
    user_id?: string;
    organization_id?: string;
    project_id?: string;
  }
}

declare module '@/utils/api-client/interfaces/status' {
  import { UUID } from 'crypto';

  export interface Status {
    id: UUID;
    name: string;
    description?: string;
    entity_type: string;
    user_id?: UUID | null;
    organization_id: UUID;
  }

  export interface StatusesQueryParams {
    skip?: number;
    limit?: number;
    entity_type?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    $filter?: string;
  }
}

declare module '@/utils/api-client/interfaces/organization' {
  import { UUID } from 'crypto';

  export interface Organization {
    id: string;
    name: string;
    display_name?: string;
    description?: string;
    website?: string;
    logo_url?: string;
    email?: string;
    phone?: string;
    address?: string;
    is_active?: boolean;
    max_users?: number;
    subscription_ends_at?: string;
    domain?: string;
    is_domain_verified?: boolean;
    createdAt: string;
    owner_id: UUID;
    user_id: UUID;
  }
}

declare module '@/utils/api-client/interfaces/tag' {
  import { UUID } from 'crypto';

  export enum EntityType {
    TEST = "Test",
    TEST_SET = "TestSet",
    TEST_RUN = "TestRun",
    TEST_RESULT = "TestResult",
    PROMPT = "Prompt",
    PROMPT_TEMPLATE = "PromptTemplate",
    BEHAVIOR = "Behavior",
    CATEGORY = "Category",
    ENDPOINT = "Endpoint",
    USE_CASE = "UseCase",
    RESPONSE_PATTERN = "ResponsePattern",
    PROJECT = "Project",
    ORGANIZATION = "Organization"
  }

  export interface TagBase {
    name: string;
    icon_unicode?: string;
    organization_id?: UUID;
    user_id?: UUID;
  }

  export interface TagCreate extends TagBase {}

  export interface TagUpdate extends Partial<TagBase> {}

  export interface Tag extends TagBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }

  export interface TagAssignment {
    entity_id: UUID;
    entity_type: EntityType;
  }
}

declare module '@/utils/api-client/interfaces/test-run' {
  import { UUID } from 'crypto';
  import { UserReference, Status, TestTag } from '@/utils/api-client/interfaces/tests';
  import { TestConfigurationDetail } from '@/utils/api-client/interfaces/test-configuration';
  import { OrganizationReference } from '@/utils/api-client/interfaces/organization';

  export interface TestRunBase {
    name?: string;
    user_id?: UUID;
    organization_id?: UUID;
    status_id?: UUID;
    attributes?: Record<string, any>;
    test_configuration_id?: UUID;
    owner_id?: UUID;
    assignee_id?: UUID;
    tags?: TestTag[];
  }

  export interface TestRunCreate extends TestRunBase {}

  export interface TestRunUpdate extends Partial<TestRunBase> {}

  export interface TestRun extends TestRunBase {
    id: UUID;
    created_at: string;
    updated_at: string;
  }

  export interface TestRunDetail extends TestRun {
    name?: string;
    user?: UserReference;
    status?: Status;
    test_configuration?: TestConfigurationDetail;
    organization?: OrganizationReference;
    priority?: number;
    assignee?: UserReference;
    owner?: UserReference;
  }
}

declare module '@/utils/api-client/interfaces/test-set' {
  import { UUID } from 'crypto';
  import { Status } from '@/utils/api-client/interfaces/status';
  import { User } from '@/utils/api-client/interfaces/user';

  export interface TestSetTag {
    id: UUID;
    name: string;
    icon_unicode?: string;
  }

  export interface Organization {
    id: UUID;
    name: string;
    description?: string;
    email?: string;
    user_id?: UUID;
    tags?: Array<{
      id: UUID;
      name: string;
      icon_unicode?: string;
    }>;
  }

  export interface LicenseType {
    id: UUID;
    description?: string;
    type_name?: string;
    type_value?: string;
    user_id?: UUID;
    organization_id?: UUID;
  }

  export interface TestSet {
    id: UUID;
    name: string;
    description?: string;
    short_description?: string;
    slug?: string;
    status_id?: UUID;
    status: string | Status;
    status_details?: Status;
    tags?: TestSetTag[];
    license_type_id?: UUID;
    license_type?: LicenseType;
    attributes?: {
      metadata?: {
        total_prompts?: number;
        categories?: string[];
        behaviors?: string[];
        use_cases?: string[];
        topics?: string[];
        sample?: string;
        license_type?: string;
      };
      topics?: string[];
      behaviors?: string[];
      use_cases?: string[];
      categories?: string[];
    };
    user_id?: UUID;
    user?: User;
    owner_id?: UUID;
    owner?: User;
    assignee_id?: UUID;
    assignee?: User;
    priority?: number;
    organization_id?: UUID;
    organization?: Organization;
    is_published: boolean;
    visibility?: 'public' | 'organization' | 'user';
  }

  export interface TestSetStatsHistorical {
    period: string;
    start_date: string;
    end_date: string;
    monthly_counts: Record<string, number>;
  }

  export interface TestSetDetailStatsResponse {
    total: number;
    stats: {
      [dimension: string]: {
        dimension: string;
        total: number;
        breakdown: {
          [key: string]: number;
        };
      };
    };
    metadata: {
      generated_at: string;
      organization_id: string;
      entity_type: string;
      source_entity_type: string;
      source_entity_id: string;
    };
    history?: TestSetStatsHistorical;
  }
}

declare module '@/utils/api-client/organizations-client' {
  import { UUID } from 'crypto';

  export interface OrganizationCreate {
    name: string;
    website?: string;
    owner_id: UUID;
    user_id: UUID;
    is_active: boolean;
    is_domain_verified: boolean;
  }
} 