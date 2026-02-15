/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import EndpointDetail from '../EndpointDetail';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

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

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getProjects: jest.fn().mockResolvedValue([]) }),
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
  status: { id: 'status-1', name: 'Active' },
};

// ---- Tests ----

describe('EndpointDetail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the endpoint name and action buttons', () => {
    render(<EndpointDetail endpoint={baseEndpoint} />);

    expect(screen.getByText('My Endpoint')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /playground/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /duplicate/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('shows Playground, Duplicate, Edit in correct order', () => {
    render(<EndpointDetail endpoint={baseEndpoint} />);

    const buttons = screen
      .getAllByRole('button')
      .filter(btn =>
        ['Playground', 'Duplicate', 'Edit'].some(label =>
          btn.textContent?.includes(label)
        )
      );

    expect(buttons).toHaveLength(3);
    expect(buttons[0]).toHaveTextContent('Playground');
    expect(buttons[1]).toHaveTextContent('Duplicate');
    expect(buttons[2]).toHaveTextContent('Edit');
  });

  describe('Duplicate endpoint', () => {
    it('calls createEndpoint with copied data and "(copy)" suffix on success', async () => {
      const duplicatedEndpoint = {
        ...baseEndpoint,
        id: 'ep-2',
        name: 'My Endpoint (copy)',
      };
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: duplicatedEndpoint,
      });

      render(<EndpointDetail endpoint={baseEndpoint} />);

      const duplicateBtn = screen.getByRole('button', { name: /duplicate/i });
      await userEvent.click(duplicateBtn);

      await waitFor(() => {
        expect(mockCreateEndpoint).toHaveBeenCalledTimes(1);
      });

      // Verify the payload sent to createEndpoint
      const payload = mockCreateEndpoint.mock.calls[0][0];
      expect(payload.name).toBe('My Endpoint (copy)');
      // Server-managed fields must be stripped
      expect(payload).not.toHaveProperty('id');
      expect(payload).not.toHaveProperty('status');
      expect(payload).not.toHaveProperty('status_id');
      expect(payload).not.toHaveProperty('user_id');
      expect(payload).not.toHaveProperty('organization_id');
      // Configuration fields must be preserved
      expect(payload.url).toBe('https://api.example.com/chat');
      expect(payload.method).toBe('POST');
      expect(payload.connection_type).toBe('REST');
      expect(payload.environment).toBe('production');
      expect(payload.request_mapping).toEqual({ input: '{{ input }}' });
      expect(payload.response_mapping).toEqual({ output: '{{ message }}' });
    });

    it('navigates to the new endpoint on success', async () => {
      mockCreateEndpoint.mockResolvedValue({
        success: true,
        data: { ...baseEndpoint, id: 'ep-new' },
      });

      render(<EndpointDetail endpoint={baseEndpoint} />);

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

      render(<EndpointDetail endpoint={baseEndpoint} />);

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

      render(<EndpointDetail endpoint={baseEndpoint} />);

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

      render(<EndpointDetail endpoint={baseEndpoint} />);

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

  describe('action buttons visibility', () => {
    it('hides Duplicate and Playground when in edit mode', async () => {
      render(<EndpointDetail endpoint={baseEndpoint} />);

      // Enter edit mode
      await userEvent.click(screen.getByRole('button', { name: /edit/i }));

      // Save and Cancel should appear
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /cancel/i })
      ).toBeInTheDocument();

      // Duplicate and Playground should not be visible
      expect(
        screen.queryByRole('button', { name: /duplicate/i })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: /playground/i })
      ).not.toBeInTheDocument();
    });

    it('restores action buttons when cancelling edit mode', async () => {
      render(<EndpointDetail endpoint={baseEndpoint} />);

      await userEvent.click(screen.getByRole('button', { name: /edit/i }));
      await userEvent.click(screen.getByRole('button', { name: /cancel/i }));

      expect(
        screen.getByRole('button', { name: /duplicate/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /playground/i })
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });
  });

  it('navigates to playground with endpoint ID', async () => {
    render(<EndpointDetail endpoint={baseEndpoint} />);

    await userEvent.click(screen.getByRole('button', { name: /playground/i }));

    expect(mockPush).toHaveBeenCalledWith('/playground?endpointId=ep-1');
  });
});
