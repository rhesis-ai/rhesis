import { http, HttpResponse } from 'msw';

const BASE_URL = 'http://localhost:8080/api/v1';

/**
 * Default MSW handlers for common API endpoints.
 * Import and extend these in individual test files as needed.
 */
export const handlers = [
  // Tasks
  http.get(`${BASE_URL}/tasks`, () => {
    return HttpResponse.json(
      [
        {
          id: 'task-1',
          title: 'Test Task',
          description: 'A test task',
          status: { id: 'status-1', name: 'Open' },
          priority: { id: 'priority-1', type_value: 'Medium' },
          user: {
            id: 'user-1',
            name: 'John Doe',
            email: 'john@example.com',
          },
          assignee: null,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      {
        headers: { 'x-total-count': '1' },
      }
    );
  }),

  http.post(`${BASE_URL}/tasks`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: 'task-new',
        ...body,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 }
    );
  }),

  // Tests
  http.get(`${BASE_URL}/tests`, () => {
    return HttpResponse.json([], {
      headers: { 'x-total-count': '0' },
    });
  }),

  http.get(`${BASE_URL}/tests/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      prompt_id: 'prompt-1',
      priority: 1,
      priorityLevel: 'Medium',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    });
  }),

  http.post(`${BASE_URL}/tests`, () => {
    return HttpResponse.json(
      { id: 'new-test-id', prompt_id: 'prompt-new', priority: 1 },
      { status: 201 }
    );
  }),

  http.put(`${BASE_URL}/tests/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      prompt_id: 'prompt-1',
      priority: 1,
    });
  }),

  http.delete(`${BASE_URL}/tests/:id`, ({ params }) => {
    return HttpResponse.json({ id: params.id });
  }),

  // Endpoints
  http.get(`${BASE_URL}/endpoints`, () => {
    return HttpResponse.json([], {
      headers: { 'x-total-count': '0' },
    });
  }),

  http.get(`${BASE_URL}/endpoints/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: 'Test Endpoint',
      connection_type: 'REST',
      environment: 'development',
      config_source: 'manual',
      response_format: 'json',
    });
  }),

  http.post(`${BASE_URL}/endpoints`, () => {
    return HttpResponse.json(
      {
        id: 'new-endpoint-id',
        name: 'New Endpoint',
        connection_type: 'REST',
        environment: 'development',
        config_source: 'manual',
        response_format: 'json',
      },
      { status: 201 }
    );
  }),

  http.put(`${BASE_URL}/endpoints/:id`, ({ params }) => {
    return HttpResponse.json({ id: params.id, name: 'Updated Endpoint' });
  }),

  http.delete(`${BASE_URL}/endpoints/:id`, ({ params }) => {
    return HttpResponse.json({ id: params.id });
  }),

  // Test Runs
  http.get(`${BASE_URL}/test_runs`, () => {
    return HttpResponse.json([], {
      headers: { 'x-total-count': '0' },
    });
  }),

  http.get(`${BASE_URL}/test_runs/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: 'Test Run',
      status: { id: 'status-1', name: 'Completed' },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    });
  }),

  http.delete(`${BASE_URL}/test_runs/:id`, ({ params }) => {
    return HttpResponse.json({ id: params.id });
  }),

  // Projects
  http.get(`${BASE_URL}/projects`, () => {
    return HttpResponse.json(
      [
        {
          id: 'project-1',
          name: 'Test Project',
          description: 'A test project',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      {
        headers: { 'x-total-count': '1' },
      }
    );
  }),

  // Organizations
  http.get(`${BASE_URL}/organizations`, () => {
    return HttpResponse.json([
      {
        id: 'org-1',
        name: 'Test Organization',
        identifier: 'test-org',
      },
    ]);
  }),

  // Statuses
  http.get(`${BASE_URL}/statuses`, () => {
    return HttpResponse.json([
      { id: 'status-1', name: 'Open' },
      { id: 'status-2', name: 'In Progress' },
      { id: 'status-3', name: 'Completed' },
      { id: 'status-4', name: 'Cancelled' },
    ]);
  }),

  // Type lookups (priorities, etc.)
  http.get(`${BASE_URL}/type_lookups`, () => {
    return HttpResponse.json([
      { id: 'priority-1', type_name: 'priority', type_value: 'Low' },
      { id: 'priority-2', type_name: 'priority', type_value: 'Medium' },
      { id: 'priority-3', type_name: 'priority', type_value: 'High' },
    ]);
  }),

  // Comments
  http.get(`${BASE_URL}/comments`, () => {
    return HttpResponse.json([], {
      headers: { 'x-total-count': '0' },
    });
  }),

  // Tags
  http.get(`${BASE_URL}/tags`, () => {
    return HttpResponse.json([]);
  }),

  // Files
  http.get(`${BASE_URL}/tests/:testId/files`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${BASE_URL}/files/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      nano_id: 'abc123',
      filename: 'test-file.png',
      content_type: 'image/png',
      size_bytes: 1024,
      entity_id: 'test-1',
      entity_type: 'Test',
      position: 0,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    });
  }),

  http.get(`${BASE_URL}/files/:id/content`, () => {
    return new HttpResponse(new Uint8Array([137, 80, 78, 71]), {
      headers: { 'Content-Type': 'image/png' },
    });
  }),

  http.post(`${BASE_URL}/files`, () => {
    return HttpResponse.json(
      [
        {
          id: 'file-new',
          nano_id: 'xyz789',
          filename: 'uploaded.png',
          content_type: 'image/png',
          size_bytes: 2048,
          entity_id: 'test-1',
          entity_type: 'Test',
          position: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      { status: 201 }
    );
  }),

  http.delete(`${BASE_URL}/files/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      filename: 'deleted-file.png',
      content_type: 'image/png',
      size_bytes: 1024,
      entity_id: 'test-1',
      entity_type: 'Test',
      position: 0,
    });
  }),
];
