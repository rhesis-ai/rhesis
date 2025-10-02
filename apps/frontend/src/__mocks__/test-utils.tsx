import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

// Create a theme for tests
const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

// Mock Next.js session
const mockSession = {
  user: {
    id: 'user-1',
    name: 'John Doe',
    email: 'john@example.com',
  },
  session_token: 'mock-session-token',
  expires: '2024-12-31T23:59:59Z',
};

// Mock NextAuth
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: mockSession,
    status: 'authenticated',
  }),
  signIn: jest.fn(),
  signOut: jest.fn(),
}));

// Providers wrapper for testing
interface AllTheProvidersProps {
  children: React.ReactNode;
}

const AllTheProviders = ({ children }: AllTheProvidersProps) => {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
};

// Custom render function
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Test data factories
export const createMockModel = (overrides = {}) => ({
  id: 'mock-model-id',
  name: 'Mock Model',
  description: 'A mock model for testing',
  icon: 'mock-icon',
  model_name: 'mock-model-name',
  endpoint: 'https://mock.endpoint.com',
  key: 'mock-key',
  request_headers: {},
  tags: ['mock-tag'],
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  provider_type: { id: 'provider-1', name: 'Mock Provider' },
  status: { id: 'status-1', name: 'Active' },
  owner: { id: 'user-1', name: 'John Doe', email: 'john@example.com' },
  assignee: null,
  metrics: [],
  ...overrides,
});

export const createMockProject = (overrides = {}) => ({
  id: 'mock-project-id',
  name: 'Mock Project',
  description: 'A mock project for testing',
  visibility: 'private',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  owner: { id: 'user-1', name: 'John Doe', email: 'john@example.com' },
  organization: { id: 'org-1', name: 'Mock Organization' },
  ...overrides,
});

export const createMockTest = (overrides = {}) => ({
  id: 'mock-test-id',
  name: 'Mock Test',
  description: 'A mock test for testing',
  prompt: 'Mock prompt for testing',
  expected_result: 'Expected mock result',
  status: { id: 'status-1', name: 'Pending' },
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  owner: { id: 'user-1', name: 'John Doe' },
  ...overrides,
});

export const createMockComment = (overrides = {}) => ({
  id: 'mock-comment-id',
  message: 'Mock comment message',
  entity_type: 'Test',
  entity_id: 'test-123',
  parent_id: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  author: { id: 'user-1', name: 'John Doe', email: 'john@example.com' },
  ...overrides,
});

export const createMockTask = (overrides = {}) => ({
  id: 'mock-task-id',
  title: 'Mock Task',
  description: 'A mock task for testing',
  status: { id: 'status-1', name: 'Open' },
  priority: 1,
  entity_type: 'Test',
  entity_id: 'test-123',
  due_date: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  assignee: null,
  owner: { id: 'user-1', name: 'John Doe' },
  ...overrides,
});

// Re-export everything from React Testing Library
export * from '@testing-library/react';
export { customRender as render };
export type { AllTheProvidersProps };
