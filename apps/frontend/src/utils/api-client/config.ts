if (!process.env.NEXT_PUBLIC_API_BASE_URL) {
  throw new Error('NEXT_PUBLIC_API_BASE_URL environment variable is not defined');
}

console.log('API_CONFIG: baseUrl set to:', process.env.NEXT_PUBLIC_API_BASE_URL);

export const API_CONFIG = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
  defaultHeaders: {
    'Content-Type': 'application/json',
  },
} as const;

// Type for endpoints to ensure type safety
export const API_ENDPOINTS = {
  tests: '/tests',
  testSets: '/test_sets',
  tokens: '/tokens',
  services: '/services',
  endpoints: '/endpoints',
  organizations: '/organizations',
  users: '/users',
  projects: '/projects', 
  testRuns: '/test_runs',
  testResults: '/test_results',
  testConfigurations: '/test_configurations',
  prompts: '/prompts',
  statuses: '/statuses',
  tags: '/tags',
  behaviors: '/behaviors',
  topics: '/topics',
  categories: '/categories',
  type_lookups: '/type_lookups',
  metrics: '/metrics',
  models: '/models'
} as const; 

export const ENTITY_TYPES = {
  test: 'Test',
  testSet: 'TestSet',
  token: 'Token',
  service: 'Service',
  endpoint: 'Endpoint',
  organization: 'Organization',
  user: 'User',
  project: 'Project',
  testRun: 'TestRun',
  testResult: 'TestResult',
  testConfiguration: 'TestConfiguration',
  prompt: 'Prompt',
  status: 'Status',
  tag: 'Tag',
  behavior: 'Behavior',
  topic: 'Topic',
  category: 'Category',
} as const;
