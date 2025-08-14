// Determine the appropriate base URL based on environment
// Use BACKEND_URL for server-side calls (container-to-container)
// Use NEXT_PUBLIC_API_BASE_URL for client-side calls (browser-to-host)
const getBaseUrl = () => {
  if (typeof window === 'undefined') {
    // Server-side: use BACKEND_URL for container-to-container communication
    return process.env.BACKEND_URL || 'http://backend:8080';
  } else {
    // Client-side: use NEXT_PUBLIC_API_BASE_URL for browser-to-host communication
    return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
  }
};

if (!process.env.NEXT_PUBLIC_API_BASE_URL) {
  throw new Error('NEXT_PUBLIC_API_BASE_URL environment variable is not defined');
}

console.log('API_CONFIG: baseUrl set to:', getBaseUrl());

export const API_CONFIG = {
  baseUrl: getBaseUrl(),
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
