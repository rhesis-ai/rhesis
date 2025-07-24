# ⚛️ Frontend Testing Guide

> **React + TypeScript testing patterns for the Rhesis frontend** 🎨

This guide covers React/TypeScript testing patterns, component testing, and frontend-specific testing strategies for the Rhesis platform.

## 📋 Table of Contents

- [🏗️ Frontend Test Architecture](#%EF%B8%8F-frontend-test-architecture)
- [⚙️ Configuration & Setup](#%EF%B8%8F-configuration--setup)
- [🧩 Component Testing](#-component-testing)
- [🔗 Integration Testing](#-integration-testing)
- [🌐 E2E Testing](#-e2e-testing)
- [🎭 Mocking & Fixtures](#-mocking--fixtures)
- [🎨 Visual & Accessibility Testing](#-visual--accessibility-testing)
- [🚀 Performance Testing](#-performance-testing)
- [🔒 Frontend Security Testing](#-frontend-security-testing)

## 🏗️ Frontend Test Architecture

### 📁 Directory Structure
```
tests/frontend/
├── 📖 README.md              # This guide
├── ⚙️ setup.ts              # Test setup configuration
├── 🧪 components/           # Component tests
│   ├── ui/                  # UI component tests
│   │   ├── Button.test.tsx
│   │   ├── TestSetCard.test.tsx
│   │   └── Badge.test.tsx
│   ├── forms/               # Form component tests
│   │   ├── LoginForm.test.tsx
│   │   ├── TestSetForm.test.tsx
│   │   └── PromptInput.test.tsx
│   └── layout/              # Layout component tests
│       ├── NavigationBar.test.tsx
│       ├── Sidebar.test.tsx
│       └── Header.test.tsx
├── 🪝 hooks/                # Custom hook tests
│   ├── useTestSets.test.ts
│   ├── useAuth.test.ts
│   └── useDataFetching.test.ts
├── 🔌 services/             # Frontend service tests
│   ├── api.test.ts
│   ├── auth.test.ts
│   └── storage.test.ts
├── 🛠️ utils/               # Frontend utility tests
│   ├── validation.test.ts
│   ├── formatters.test.ts
│   └── helpers.test.ts
├── 🔗 integration/          # Integration tests
│   ├── api-integration.test.ts
│   ├── auth-flow.test.ts
│   └── test-generation-flow.test.ts
└── 🌐 e2e/                  # End-to-end tests
    ├── user-journey.spec.ts
    ├── test-creation.spec.ts
    └── dashboard.spec.ts
```

### 🎯 Frontend-Specific Testing Layers

```typescript
// Testing pyramid for React apps
// 
// 🌐 E2E Tests (Few, Slow, High Confidence)
//     ├── Critical user journeys
//     ├── Cross-browser compatibility
//     └── Full workflow validation
//
// 🔗 Integration Tests (Some, Medium Speed)
//     ├── Component integration
//     ├── API communication
//     └── State management
//
// 🧩 Unit Tests (Many, Fast, Low-Level)
//     ├── Pure functions
//     ├── Custom hooks
//     ├── Utility functions
//     └── Component logic
```

## ⚙️ Configuration & Setup

### 📦 Dependencies
```json
{
  "devDependencies": {
    "@testing-library/react": "^13.0.0",
    "@testing-library/jest-dom": "^5.16.0",
    "@testing-library/user-event": "^14.0.0",
    "@playwright/test": "^1.28.0",
    "jest": "^29.0.0",
    "jest-environment-jsdom": "^29.0.0",
    "@axe-core/react": "^4.7.0",
    "msw": "^0.49.0"
  }
}
```

### ⚙️ Jest Configuration
```javascript
// jest.config.js
module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/frontend/setup.ts'],
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy'
  },
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/main.tsx',
    '!src/vite-env.d.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
```

### 🛠️ Test Setup
```typescript
// tests/frontend/setup.ts
import '@testing-library/jest-dom';
import { server } from './mocks/server';

// MSW Mock Server Setup
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock window.matchMedia for responsive components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));
```

## 🧩 Component Testing

### 🎨 Basic Component Testing
```typescript
// TestSetCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TestSetCard } from '@/components/TestSetCard';

describe('TestSetCard', () => {
  const mockTestSet = {
    id: '1',
    name: 'Banking Chatbot Tests',
    description: 'Comprehensive tests for banking domain',
    testCases: 15,
    domain: 'finance',
    createdAt: '2024-01-01T00:00:00Z'
  };

  it('renders test set information correctly', () => {
    render(<TestSetCard testSet={mockTestSet} />);
    
    expect(screen.getByText('Banking Chatbot Tests')).toBeInTheDocument();
    expect(screen.getByText('15 test cases')).toBeInTheDocument();
    expect(screen.getByText('finance')).toBeInTheDocument();
  });

  it('calls onSelect when card is clicked', async () => {
    const user = userEvent.setup();
    const mockOnSelect = jest.fn();
    
    render(<TestSetCard testSet={mockTestSet} onSelect={mockOnSelect} />);
    
    await user.click(screen.getByRole('button', { name: /select test set/i }));
    
    expect(mockOnSelect).toHaveBeenCalledWith(mockTestSet.id);
  });

  it('shows loading state when test set is being processed', () => {
    render(<TestSetCard testSet={mockTestSet} isLoading={true} />);
    
    expect(screen.getByLabelText(/loading/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### 🪝 Testing Custom Hooks
```typescript
// useTestSets.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTestSets } from '@/hooks/useTestSets';
import * as api from '@/services/api';

// Mock the API
jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('useTestSets', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('fetches test sets successfully', async () => {
    const mockTestSets = [
      { id: '1', name: 'Test Set 1' },
      { id: '2', name: 'Test Set 2' }
    ];
    
    mockedApi.getTestSets.mockResolvedValue(mockTestSets);
    
    const { result } = renderHook(() => useTestSets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockTestSets);
    expect(mockedApi.getTestSets).toHaveBeenCalledTimes(1);
  });

  it('handles error states correctly', async () => {
    const errorMessage = 'Failed to fetch test sets';
    mockedApi.getTestSets.mockRejectedValue(new Error(errorMessage));
    
    const { result } = renderHook(() => useTestSets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });
});
```

### 🎯 Testing with Context
```typescript
// AuthProvider.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';

const TestComponent = () => {
  const { user, login, logout } = useAuth();
  
  return (
    <div>
      {user ? (
        <div>
          <span>Welcome, {user.name}</span>
          <button onClick={logout}>Logout</button>
        </div>
      ) : (
        <button onClick={() => login('test@example.com', 'password')}>
          Login
        </button>
      )}
    </div>
  );
};

describe('AuthProvider', () => {
  it('provides authentication functionality', async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Initially logged out
    expect(screen.getByText('Login')).toBeInTheDocument();

    // Simulate login
    fireEvent.click(screen.getByText('Login'));
    
    // Should show logged in state
    expect(await screen.findByText(/Welcome/)).toBeInTheDocument();
  });
});
```

## 🔗 Integration Testing

### 🌐 API Integration Testing
```typescript
// api-integration.test.ts
import { rest } from 'msw';
import { server } from '../mocks/server';
import { ApiClient } from '@/services/api';

describe('API Integration', () => {
  const apiClient = new ApiClient('http://localhost:3000');

  it('creates test set successfully', async () => {
    const newTestSet = {
      name: 'Integration Test Set',
      description: 'Created via integration test',
      prompt: 'Generate tests for integration testing'
    };

    server.use(
      rest.post('/api/v1/test-sets', (req, res, ctx) => {
        return res(
          ctx.status(201),
          ctx.json({
            id: 'new-test-set-id',
            ...newTestSet,
            testCases: []
          })
        );
      })
    );

    const result = await apiClient.createTestSet(newTestSet);

    expect(result.id).toBe('new-test-set-id');
    expect(result.name).toBe(newTestSet.name);
  });

  it('handles authentication errors', async () => {
    server.use(
      rest.get('/api/v1/user/profile', (req, res, ctx) => {
        return res(ctx.status(401), ctx.json({ error: 'Unauthorized' }));
      })
    );

    await expect(apiClient.getUserProfile()).rejects.toThrow('Unauthorized');
  });
});
```

### 🎯 Component Integration Testing
```typescript
// test-generation-flow.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TestGenerationFlow } from '@/components/TestGenerationFlow';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

describe('Test Generation Flow Integration', () => {
  const renderWithProvider = (component: React.ReactElement) => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    });
    
    return render(
      <QueryClientProvider client={queryClient}>
        {component}
      </QueryClientProvider>
    );
  };

  it('completes full test generation workflow', async () => {
    const user = userEvent.setup();
    
    renderWithProvider(<TestGenerationFlow />);

    // Step 1: Enter prompt
    const promptInput = screen.getByLabelText(/prompt/i);
    await user.type(promptInput, 'Generate tests for a banking chatbot');

    // Step 2: Configure options
    const countInput = screen.getByLabelText(/number of tests/i);
    await user.clear(countInput);
    await user.type(countInput, '10');

    // Step 3: Generate tests
    const generateButton = screen.getByRole('button', { name: /generate/i });
    await user.click(generateButton);

    // Step 4: Verify generation started
    expect(screen.getByText(/generating/i)).toBeInTheDocument();

    // Step 5: Verify completion
    await waitFor(() => {
      expect(screen.getByText(/generation complete/i)).toBeInTheDocument();
    }, { timeout: 5000 });

    // Step 6: Verify test cases are displayed
    expect(screen.getAllByTestId('test-case-item')).toHaveLength(10);
  });
});
```

## 🌐 E2E Testing

### 🎭 Playwright E2E Tests
```typescript
// e2e/user-journey.spec.ts
import { test, expect } from '@playwright/test';

test.describe('User Journey', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses
    await page.route('/api/v1/**', (route) => {
      if (route.request().url().includes('/test-sets')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: '1', name: 'Sample Test Set', testCases: 5 }
          ])
        });
      }
    });
  });

  test('user can create and manage test sets', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard');

    // Create new test set
    await page.click('[data-testid="create-test-set-button"]');
    
    // Fill in test set details
    await page.fill('[data-testid="test-set-name"]', 'E2E Test Set');
    await page.fill('[data-testid="test-set-description"]', 'Created via E2E test');
    await page.fill('[data-testid="prompt-input"]', 'Generate tests for e2e testing');
    
    // Submit form
    await page.click('[data-testid="submit-button"]');
    
    // Verify creation
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
    await expect(page.locator('text=E2E Test Set')).toBeVisible();
  });

  test('user can navigate between pages', async ({ page }) => {
    await page.goto('/');
    
    // Test navigation
    await page.click('text=Dashboard');
    await expect(page).toHaveURL('/dashboard');
    
    await page.click('text=Test Sets');
    await expect(page).toHaveURL('/test-sets');
    
    await page.click('text=Profile');
    await expect(page).toHaveURL('/profile');
  });
});
```

### 🌐 Cross-Browser Testing
```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/frontend/e2e',
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
});
```

## 🎭 Mocking & Fixtures

### 🛠️ MSW API Mocking
```typescript
// mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  // Test Sets API
  rest.get('/api/v1/test-sets', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
        {
          id: '1',
          name: 'Banking Tests',
          description: 'Tests for banking chatbot',
          testCases: 10,
          domain: 'finance'
        }
      ])
    );
  }),

  rest.post('/api/v1/test-sets', (req, res, ctx) => {
    const newTestSet = req.body as any;
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-id',
        ...newTestSet,
        testCases: []
      })
    );
  }),

  // Authentication API
  rest.post('/api/v1/auth/login', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        token: 'mock-jwt-token',
        user: {
          id: 'user-1',
          name: 'Test User',
          email: 'test@example.com'
        }
      })
    );
  }),
];
```

### 🎯 Test Utilities
```typescript
// test-utils.tsx
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          {children}
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

export * from '@testing-library/react';
export { customRender as render };
```

## 🎨 Visual & Accessibility Testing

### ♿ Accessibility Testing
```typescript
// accessibility.test.tsx
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { TestSetCard } from '@/components/TestSetCard';

expect.extend(toHaveNoViolations);

describe('Accessibility Tests', () => {
  it('TestSetCard should be accessible', async () => {
    const { container } = render(
      <TestSetCard testSet={mockTestSet} />
    );
    
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('supports keyboard navigation', async () => {
    const user = userEvent.setup();
    render(<TestSetCard testSet={mockTestSet} onSelect={mockOnSelect} />);
    
    const button = screen.getByRole('button');
    
    // Tab to button
    await user.tab();
    expect(button).toHaveFocus();
    
    // Activate with keyboard
    await user.keyboard('{Enter}');
    expect(mockOnSelect).toHaveBeenCalled();
  });
});
```

### 📱 Responsive Testing
```typescript
// responsive.test.tsx
import { render, screen } from '@testing-library/react';
import { Navigation } from '@/components/Navigation';

describe('Responsive Behavior', () => {
  it('shows mobile menu on small screens', () => {
    // Mock small screen
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 640,
    });
    
    render(<Navigation />);
    
    expect(screen.getByLabelText(/menu/i)).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeVisible();
  });

  it('shows full navigation on large screens', () => {
    // Mock large screen
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024,
    });
    
    render(<Navigation />);
    
    expect(screen.getByRole('navigation')).toBeVisible();
    expect(screen.queryByLabelText(/menu/i)).not.toBeInTheDocument();
  });
});
```

## 🔒 Frontend Security Testing

### 🛡️ XSS Protection Testing
```typescript
// security.test.tsx
import { render, screen } from '@testing-library/react';
import { TestSetDisplay } from '@/components/TestSetDisplay';

describe('Security Tests', () => {
  it('sanitizes user input to prevent XSS', () => {
    const maliciousTestSet = {
      id: '1',
      name: '<script>alert("xss")</script>Malicious Test Set',
      description: '<img src="x" onerror="alert(\'xss\')" />Test description'
    };
    
    render(<TestSetDisplay testSet={maliciousTestSet} />);
    
    // Verify script tags are not executed
    expect(screen.queryByText(/alert/)).not.toBeInTheDocument();
    
    // Verify content is properly escaped
    const nameElement = screen.getByText(/Malicious Test Set/);
    expect(nameElement.innerHTML).not.toContain('<script>');
  });

  it('validates input fields', async () => {
    const user = userEvent.setup();
    render(<CreateTestSetForm />);
    
    // Try to submit with malicious content
    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, '<script>malicious()</script>');
    
    const submitButton = screen.getByRole('button', { name: /create/i });
    await user.click(submitButton);
    
    // Should show validation error
    expect(screen.getByText(/invalid characters/i)).toBeInTheDocument();
  });
});
```

## 🚀 Running Frontend Tests

```bash
# Jest Tests
npm test                                  # All Jest tests (components, hooks, etc.)
npm test -- --watch                      # Watch mode for development
npm test -- --coverage                   # Coverage report

# Run specific test types
npm test tests/frontend/components/       # All component tests
npm test tests/frontend/hooks/           # All custom hook tests
npm test tests/frontend/services/        # All frontend service tests

# Run specific component categories
npm test tests/frontend/components/ui/    # UI component tests only
npm test tests/frontend/components/forms/ # Form component tests only

# Run by pattern
npm test Button                          # All tests with "Button" in name
npm test -- --testNamePattern="accessibility" # Accessibility tests only

# Playwright E2E Tests
npx playwright test                      # All E2E tests
npx playwright test --ui                 # Run with Playwright UI
npx playwright test --headed             # Run in headed mode (see browser)
npx playwright test tests/frontend/e2e/user-journey.spec.ts # Specific test file

# Debug specific E2E test
npx playwright test --debug tests/frontend/e2e/login.spec.ts
```

## 📚 Additional Resources

- [React Testing Library Documentation](https://testing-library.com/docs/react-testing-library/intro/)
- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [Playwright Documentation](https://playwright.dev/)
- [Accessibility Testing Guide](https://web.dev/accessibility-testing/)
- [Main Testing Guide](../README.md) - Universal testing principles

---

**⚛️ Happy React Testing!** 🎨 