# Frontend Testing Guide

This directory contains the testing infrastructure and test files for the Rhesis frontend application.

## 📁 Test Structure

```
src/__tests__/
├── README.md                           # This guide
├── integration/                        # Integration tests
│   └── api-client.integration.test.ts  # API client integration tests
└── __mocks__/                         # Test mocks and utilities
    ├── msw/                           # Mock Service Worker setup
    │   └── server.ts                  # API mocking server
    └── test-utils.tsx                 # Testing utilities and helpers
```

Additional test files are located alongside their source code:

- Component tests: `src/components/**/__tests__/*.test.tsx`
- Hook tests: `src/hooks/__tests__/*.test.ts`
- Utility tests: `src/utils/**/__tests__/*.test.ts`

## 🧪 Test Categories

### Unit Tests

- **Component Tests**: Test React components in isolation
- **Hook Tests**: Test custom React hooks
- **Utility Tests**: Test pure functions and utilities

### Integration Tests

- **API Client Tests**: Test API client interactions with mocked backend
- **Component Integration**: Test component interactions with external APIs

## 🚀 Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode (development)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run tests for CI (single run)
npm run test:ci

# Run specific test files
npm test BaseDrawer.test.tsx
npm test api-client.integration.test.ts

# Run tests by pattern
npm test -- --testNamePattern="API Client"
npm test -- --testPathPattern="components"
```

## 📦 Testing Libraries

- **Jest**: Test runner and assertion library
- **React Testing Library**: Component testing utilities
- **MSW (Mock Service Worker)**: API mocking for integration tests
- **User Event**: User interaction simulation
- **jest-axe**: Accessibility testing

## 🔧 Configuration Files

- `jest.config.js`: Jest configuration for Next.js
- `jest.setup.js`: Global test setup and mocks

## 🎭 Mocking Strategy

### API Mocking with MSW

MSW (Mock Service Worker) intercepts API calls during tests, allowing us to:

- Test API integration without real backend
- Simulate different response scenarios (success, errors, loading states)
- Test error handling and edge cases

### Component Mocking

- Next.js router is mocked for consistent navigation testing
- Material-UI ThemeProvider is provided for consistency
- Notification context is mocked to avoid side effects

## 📋 Test Best Practices

### Writing Component Tests

1. **Test behavior, not implementation**: Focus on what users can see and do
2. **Use semantic queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
3. **Test accessibility**: Include basic accessibility checks
4. **Mock external dependencies**: Don't test third-party libraries
5. **Clean up**: Reset mocks between tests

### Writing Hook Tests

1. **Test state changes**: Verify state updates correctly
2. **Test side effects**: Check async operations and API calls
3. **Test error handling**: Ensure errors are handled gracefully
4. **Mock external dependencies**: Use jest.mock for API clients

### Writing Integration Tests

1. **Test real API interactions**: Use MSW to simulate backend responses
2. **Test error scenarios**: Network failures, validation errors, etc.
3. **Test data flow**: Verify data flows correctly between components and APIs
4. **Test user workflows**: End-to-end user interactions

## 🎯 Coverage Goals

- **Components**: 80%+ line coverage
- **Hooks**: 90%+ line coverage
- **Utils**: 95%+ line coverage
- **Integration**: Critical user flows covered

## 📝 Test Data Factories

Test data factories are provided in `test-utils.tsx` for creating consistent mock data:

```typescript
import { createMockModel, createMockProject } from '../__mocks__/test-utils';

const mockModel = createMockModel({ name: 'Custom Model' });
const mockProject = createMockProject({ visibility: 'public' });
```

## 🔍 Debugging Tests

### Common Issues

1. **Async timing**: Use `waitFor` for async operations
2. **Mock not working**: Check mock setup and implementation
3. **DOM not found**: Ensure component renders before querying
4. **State not updating**: Use `act` for state updates

### Debugging Tips

```bash
# Run single test file with verbose output
npm test BaseDrawer.test.tsx -- --verbose

# Debug test with Node inspector
node --inspect-brk node_modules/.bin/jest --runInBand

# Check test coverage for specific files
npm run test:coverage -- --testPathPattern="BaseDrawer"
```

## 📚 Additional Resources

- [React Testing Library Documentation](https://testing-library.com/docs/react-testing-library/intro/)
- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [MSW Documentation](https://mswjs.io/)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
