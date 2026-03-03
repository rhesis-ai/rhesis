import { ProjectsClient } from '../projects-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';

function makeFetchResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (key: string) => headers[key.toLowerCase()] ?? null,
      entries: () => Object.entries(headers),
    },
    json: () => Promise.resolve(body),
    text: () =>
      Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response);
}

const mockProject = {
  id: 'proj-1',
  name: 'My Project',
  description: 'Test project',
  created_at: '2024-01-01',
  updated_at: '2024-01-01',
};

describe('ProjectsClient', () => {
  let client: ProjectsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new ProjectsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getProjects', () => {
    it('fetches projects with default pagination', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ data: [mockProject], total: 1 }, 200, {
          'x-total-count': '1',
        }) as unknown as Response
      );

      await client.getProjects();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(`${BASE_URL}/projects`),
        expect.objectContaining({ credentials: 'include' })
      );
    });

    it('includes skip and limit in query string', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ data: [], total: 0 }, 200, {
          'x-total-count': '0',
        }) as unknown as Response
      );

      await client.getProjects({ skip: 20, limit: 5 });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('skip=20');
      expect(calledUrl).toContain('limit=5');
    });

    it('includes $filter in query string when provided', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ data: [], total: 0 }, 200, {
          'x-total-count': '0',
        }) as unknown as Response
      );

      await client.getProjects({ $filter: "name eq 'My Project'" });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      // URLSearchParams encodes $ as %24
      expect(calledUrl).toContain('%24filter');
    });

    it('sends Authorization header', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ data: [], total: 0 }, 200, {
          'x-total-count': '0',
        }) as unknown as Response
      );

      await client.getProjects();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });

  describe('getProject', () => {
    it('fetches a single project by id', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockProject) as unknown as Response
      );

      const result = await client.getProject('proj-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1'),
        expect.anything()
      );
      expect(result.id).toBe('proj-1');
      expect(result.name).toBe('My Project');
    });

    it('throws on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404) as unknown as Response
      );

      await expect(client.getProject('missing')).rejects.toThrow(
        'API error: 404'
      );
    });
  });

  describe('createProject', () => {
    it('sends POST to /projects with project data', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockProject) as unknown as Response
      );

      await client.createProject({ name: 'My Project', description: 'desc' });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/projects'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"name":"My Project"'),
        })
      );
    });

    it('returns the created project', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockProject) as unknown as Response
      );

      const result = await client.createProject({
        name: 'My Project',
        description: 'desc',
      });

      expect(result.id).toBe('proj-1');
      expect(result.name).toBe('My Project');
    });

    it('throws on API error', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(
          { detail: 'Validation error' },
          422
        ) as unknown as Response
      );

      await expect(
        client.createProject({ name: '', description: '' })
      ).rejects.toThrow('API error: 422');
    });
  });

  describe('updateProject', () => {
    it('sends PUT to /projects/{id} with update data', async () => {
      const updatedProject = { ...mockProject, name: 'Updated Name' };
      fetchMock.mockResolvedValue(
        makeFetchResponse(updatedProject) as unknown as Response
      );

      const result = await client.updateProject('proj-1', {
        name: 'Updated Name',
      });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"name":"Updated Name"'),
        })
      );
      expect(result.name).toBe('Updated Name');
    });
  });

  describe('deleteProject', () => {
    it('sends DELETE to /projects/{id}', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(null) as unknown as Response
      );

      await client.deleteProject('proj-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('throws on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404) as unknown as Response
      );

      await expect(client.deleteProject('missing')).rejects.toThrow(
        'API error: 404'
      );
    });
  });
});
