import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/**
 * MSW server instance for use in Jest tests.
 *
 * Usage in jest.setup.js or individual test files:
 *
 *   import { server } from '@/__mocks__/msw/server';
 *
 *   beforeAll(() => server.listen());
 *   afterEach(() => server.resetHandlers());
 *   afterAll(() => server.close());
 *
 * To override handlers in specific tests:
 *
 *   import { http, HttpResponse } from 'msw';
 *
 *   server.use(
 *     http.get('http://localhost:8080/api/v1/tasks', () => {
 *       return HttpResponse.json([], { status: 200 });
 *     })
 *   );
 */
export const server = setupServer(...handlers);
