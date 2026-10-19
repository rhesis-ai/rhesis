import React from 'react';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import '@testing-library/jest-dom';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import EndpointConnectionTab from '../EndpointConnectionTab';

jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
  }: {
    value?: string;
    onChange?: (value: string) => void;
  }) => (
    <textarea
      data-testid="mock-editor"
      value={value || ''}
      onChange={e => onChange?.(e.target.value)}
    />
  ),
}));

jest.mock(
  'next/dynamic',
  () => (loader: () => Promise<{ default: React.ComponentType }>) => {
    function DynamicComponent(props: Record<string, unknown>) {
      const [Comp, setComp] = React.useState<React.ComponentType | null>(null);
      React.useEffect(() => {
        loader().then(mod => {
          setComp(() => mod.default ?? (mod as unknown as React.ComponentType));
        });
      }, []);
      if (!Comp) return null;
      return React.createElement(Comp, props);
    }
    DynamicComponent.displayName = 'DynamicComponent';
    return DynamicComponent;
  }
);

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

const mockSaveFields = jest.fn();
let mockEndpoint: Endpoint;
jest.mock('../EndpointDetailContext', () => ({
  useEndpointDetailContext: () => ({
    endpoint: mockEndpoint,
    editorTheme: 'light',
    editorWrapperStyle: {},
    saveFields: mockSaveFields,
  }),
}));

const oauthEndpoint: Endpoint = {
  id: 'ep-1',
  name: 'OAuth endpoint',
  connection_type: 'REST',
  environment: 'development',
  config_source: 'manual',
  response_format: 'json',
  url: 'https://api.example.com/chat',
  method: 'POST',
  request_headers: {},
  auth_type: 'client_credentials',
  has_client_secret: true,
  token_url: 'https://auth.example.com/oauth/token',
  client_id: 'client-123',
  scopes: ['read'],
};

function authSection() {
  const heading = screen.getByText('Authentication & headers');
  const card = heading.closest('.MuiCard-root, .MuiPaper-root');
  if (!(card instanceof HTMLElement)) throw new Error('section not found');
  return within(card);
}

describe('EndpointConnectionTab — auth type', () => {
  beforeEach(() => {
    mockEndpoint = oauthEndpoint;
    mockSaveFields.mockReset().mockResolvedValue(undefined);
    mockShow.mockReset();
  });

  it('shows a stored client-credentials endpoint as such', () => {
    render(<EndpointConnectionTab />);
    const section = authSection();
    expect(
      section.getByText('OAuth 2.0 client credentials')
    ).toBeInTheDocument();
    expect(
      section.getByText('https://auth.example.com/oauth/token')
    ).toBeInTheDocument();
    expect(section.getByText('client-123')).toBeInTheDocument();
  });

  it('can switch a client-credentials endpoint back to bearer', async () => {
    render(<EndpointConnectionTab />);
    const section = authSection();
    fireEvent.click(section.getByRole('button', { name: /edit/i }));

    fireEvent.mouseDown(
      section.getByRole('combobox', { name: 'Authentication' })
    );
    fireEvent.click(
      await screen.findByRole('option', { name: 'Bearer token' })
    );
    fireEvent.click(section.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mockSaveFields).toHaveBeenCalled());
    expect(mockSaveFields).toHaveBeenCalledWith({
      request_headers: {},
      auth_type: 'bearer_token',
    });
  });

  it('saves edited client credentials and keeps the stored secret', async () => {
    render(<EndpointConnectionTab />);
    const section = authSection();
    fireEvent.click(section.getByRole('button', { name: /edit/i }));

    fireEvent.change(section.getByLabelText(/client id/i), {
      target: { value: 'client-456' },
    });
    fireEvent.click(section.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mockSaveFields).toHaveBeenCalled());
    const payload = mockSaveFields.mock.calls[0][0];
    expect(payload.client_id).toBe('client-456');
    expect(payload).not.toHaveProperty('client_secret');
  });

  it('saves the chosen client authentication method', async () => {
    render(<EndpointConnectionTab />);
    const section = authSection();
    fireEvent.click(section.getByRole('button', { name: /edit/i }));

    fireEvent.mouseDown(
      section.getByRole('combobox', { name: 'Client authentication' })
    );
    fireEvent.click(
      await screen.findByRole('option', { name: 'In request body' })
    );
    fireEvent.click(section.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mockSaveFields).toHaveBeenCalled());
    expect(mockSaveFields.mock.calls[0][0].token_endpoint_auth_method).toBe(
      'client_secret_post'
    );
  });
});
