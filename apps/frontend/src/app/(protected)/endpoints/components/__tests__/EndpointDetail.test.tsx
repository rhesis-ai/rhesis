/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Box } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { lightTheme } from '@/styles/theme';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EndpointDetailProvider } from '../../[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '../../[identifier]/components/EndpointDetailView';
import EndpointHeaderActions from '../../[identifier]/components/EndpointHeaderActions';

function renderEndpointDetail(endpoint: Endpoint) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <EndpointDetailProvider endpoint={endpoint}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <EndpointHeaderActions />
        </Box>
        <EndpointDetailView />
      </EndpointDetailProvider>
    </ThemeProvider>
  );
}

// ---- Mocks ----

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  usePathname: () => '/endpoints/ep-1',
  useSearchParams: () => new URLSearchParams(),
}));

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { session_token: 'tok' } }),
}));

const mockDeleteEndpoint = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getProjects: jest.fn().mockResolvedValue([]) }),
    getEndpointsClient: () => ({
      deleteEndpoint: (...args: unknown[]) => mockDeleteEndpoint(...args),
    }),
  })),
}));

// Mock Monaco editor — render a plain textarea so tests don't need the real editor
jest.mock('next/dynamic', () => {
  return () => {
    const MockEditor = (props: any) => (
      <textarea
        data-testid="mock-editor"
        value={props.value}
        readOnly={props.options?.readOnly}
        onChange={e => props.onChange?.(e.target.value)}
      />
    );
    MockEditor.displayName = 'MockEditor';
    return MockEditor;
  };
});

const mockCreateEndpoint = jest.fn();
const mockUpdateEndpoint = jest.fn();
const mockInvokeEndpoint = jest.fn();
jest.mock('@/actions/endpoints', () => ({
  createEndpoint: (...args: any[]) => mockCreateEndpoint(...args),
  updateEndpoint: (...args: any[]) => mockUpdateEndpoint(...args),
  invokeEndpoint: (...args: any[]) => mockInvokeEndpoint(...args),
}));

jest.mock('@/utils/status-colors', () => ({
  getStatusColor: () => 'default' as const,
}));

// ---- Fixtures ----

const baseEndpoint: Endpoint = {
  id: 'ep-1',
  name: 'My Endpoint',
  description: 'A test endpoint',
  connection_type: 'REST',
  url: 'https://api.example.com/chat',
  method: 'POST',
  environment: 'production',
  config_source: 'manual',
  response_format: 'json',
  request_mapping: { input: '{{ input }}' },
  response_mapping: { output: '{{ message }}' },
  request_headers: { 'x-custom': 'value' },
  status_id: 'status-1',
  user_id: 'user-1',
  organization_id: 'org-1',
  project_id: 'proj-1',
  status: {
    id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    name: 'Active',
    entity_type: 'endpoint',
    organization_id: 'a1b2c3d4-0000-0000-0000-000000000001',
  },
};

// ---- Tests ----

describe('EndpointDetail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the endpoint name and action buttons', () => {
    renderEndpointDetail(baseEndpoint);

    expect(screen.getByText('My Endpoint')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /playground/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /duplicate/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /delete endpoint/i })
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /^edit$/i }).length
    ).toBeGreaterThanOrEqual(1);
  });

  it('shows Playground, Duplicate, and per-card Edit actions on overview', () => {
    renderEndpointDetail(baseEndpoint);

    expect(
      screen.getByRole('button', { name: /playground/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /duplicate/i })
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /^edit$/i })).toHaveLength(2);
  });

  describe('Duplicate endpoint', () => {
    it('calls createEndpoint with "(Copy)" suffix on success', async () => {
      const duplicatedEndpoint = {
        ...baseEndpoint,
        id: 'ep-2',
        name: 'My Endpoint (Copy)',
      };
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: duplicatedEndpoint,
      });

      renderEndpointDetail(baseEndpoint);

      const duplicateBtn = screen.getByRole('button', { name: /duplicate/i });
      await userEvent.click(duplicateBtn);

      await waitFor(() => {
        expect(mockCreateEndpoint).toHaveBeenCalledTimes(1);
      });

      // Verify the payload sent to createEndpoint
      const payload = mockCreateEndpoint.mock.calls[0][0];
      expect(payload.name).toBe('My Endpoint (Copy)');
      // Server-managed fields must be stripped
      expect(payload).not.toHaveProperty('id');
      expect(payload).not.toHaveProperty('status');
      expect(payload).not.toHaveProperty('status_id');
      expect(payload).not.toHaveProperty('user_id');
      expect(payload).not.toHaveProperty('organization_id');
      expect(payload).not.toHaveProperty('nano_id');
      expect(payload).not.toHaveProperty('created_at');
      expect(payload).not.toHaveProperty('updated_at');
      // Configuration fields must be preserved
      expect(payload.url).toBe('https://api.example.com/chat');
      expect(payload.method).toBe('POST');
      expect(payload.connection_type).toBe('REST');
      expect(payload.environment).toBe('production');
      expect(payload.request_mapping).toEqual({ input: '{{ input }}' });
      expect(payload.response_mapping).toEqual({ output: '{{ message }}' });
    });

    it('increments to "(Copy 2)" when duplicating a "(Copy)" endpoint', async () => {
      const alreadyCopied = {
        ...baseEndpoint,
        name: 'My Endpoint (Copy)',
      };
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: { ...alreadyCopied, id: 'ep-4', name: 'My Endpoint (Copy 2)' },
      });

      renderEndpointDetail(alreadyCopied);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockCreateEndpoint).toHaveBeenCalledTimes(1);
      });

      // Should produce "(Copy 2)", not "(Copy) (Copy)" or "(Copy)" again
      expect(mockCreateEndpoint.mock.calls[0][0].name).toBe(
        'My Endpoint (Copy 2)'
      );
    });

    it('increments to "(Copy 4)" when duplicating a "(Copy 3)" endpoint', async () => {
      const copy3 = { ...baseEndpoint, name: 'My Endpoint (Copy 3)' };
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: { ...copy3, id: 'ep-5', name: 'My Endpoint (Copy 4)' },
      });

      renderEndpointDetail(copy3);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockCreateEndpoint).toHaveBeenCalledTimes(1);
      });

      expect(mockCreateEndpoint.mock.calls[0][0].name).toBe(
        'My Endpoint (Copy 4)'
      );
    });

    it('navigates to the new endpoint on success', async () => {
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: { ...baseEndpoint, id: 'ep-new' },
      });

      renderEndpointDetail(baseEndpoint);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/endpoints/ep-new');
      });
    });

    it('shows success notification on duplicate', async () => {
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: { ...baseEndpoint, id: 'ep-new' },
      });

      renderEndpointDetail(baseEndpoint);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockShow).toHaveBeenCalledWith(
          'Endpoint duplicated successfully',
          { severity: 'success' }
        );
      });
    });

    it('shows error notification when API returns failure', async () => {
      mockCreateEndpoint.mockResolvedValue({
        success: false,
        error: 'Name already taken',
      });

      renderEndpointDetail(baseEndpoint);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockShow).toHaveBeenCalledWith(
          expect.stringContaining('Name already taken'),
          { severity: 'error' }
        );
      });

      // Should NOT navigate
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('shows error notification when createEndpoint throws', async () => {
      mockCreateEndpoint.mockRejectedValue(new Error('Network failure'));

      renderEndpointDetail(baseEndpoint);

      await userEvent.click(screen.getByRole('button', { name: /duplicate/i }));

      await waitFor(() => {
        expect(mockShow).toHaveBeenCalledWith(
          expect.stringContaining('Network failure'),
          { severity: 'error' }
        );
      });

      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  describe('per-card edit', () => {
    it('keeps Playground and Duplicate visible while a card is in edit mode', async () => {
      renderEndpointDetail(baseEndpoint);

      const editButtons = screen.getAllByRole('button', { name: /^edit$/i });
      await userEvent.click(editButtons[0]);

      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /cancel/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /duplicate/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /playground/i })
      ).toBeInTheDocument();
    });

    it('only puts the edited card into edit mode', async () => {
      renderEndpointDetail(baseEndpoint);

      const editButtons = screen.getAllByRole('button', { name: /^edit$/i });
      await userEvent.click(editButtons[0]);

      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(editButtons[1]).toBeInTheDocument();
      expect(screen.queryAllByRole('button', { name: /save/i })).toHaveLength(
        1
      );
    });

    it('exits edit mode for one card without affecting the other', async () => {
      renderEndpointDetail(baseEndpoint);

      const editButtons = screen.getAllByRole('button', { name: /^edit$/i });
      await userEvent.click(editButtons[0]);
      await userEvent.click(screen.getByRole('button', { name: /cancel/i }));

      expect(screen.getAllByRole('button', { name: /^edit$/i })).toHaveLength(
        2
      );
      expect(
        screen.queryByRole('button', { name: /save/i })
      ).not.toBeInTheDocument();
    });
  });

  it('navigates to playground with endpoint ID', async () => {
    renderEndpointDetail(baseEndpoint);

    await userEvent.click(screen.getByRole('button', { name: /playground/i }));

    expect(mockPush).toHaveBeenCalledWith('/playground?endpointId=ep-1');
  });

  describe('Delete endpoint', () => {
    it('deletes endpoint and navigates to endpoints list', async () => {
      mockDeleteEndpoint.mockResolvedValue(undefined);
      const standalone = { ...baseEndpoint, project_id: undefined };
      renderEndpointDetail(standalone);

      await userEvent.click(
        screen.getByRole('button', { name: /delete endpoint/i })
      );
      await userEvent.click(screen.getByRole('button', { name: /^delete$/i }));

      await waitFor(() => {
        expect(mockDeleteEndpoint).toHaveBeenCalledWith('ep-1');
      });
      expect(mockPush).toHaveBeenCalledWith('/endpoints');
      expect(mockShow).toHaveBeenCalledWith('Endpoint deleted', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    });

    it('navigates to project when endpoint belongs to a project', async () => {
      mockDeleteEndpoint.mockResolvedValue(undefined);
      renderEndpointDetail(baseEndpoint);

      await userEvent.click(
        screen.getByRole('button', { name: /delete endpoint/i })
      );
      await userEvent.click(screen.getByRole('button', { name: /^delete$/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/projects/proj-1');
      });
    });
  });
});
