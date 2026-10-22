import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

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

jest.mock('@monaco-editor/react', () => {
  const MockEditor = ({
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
  );
  return { __esModule: true, default: MockEditor };
});

import TabConnection from '../TabConnection';
import type { FormData } from '../EndpointForm';
import { ENDPOINT_AUTH_TYPES } from '@/constants/endpoint-auth';
import { EMPTY_CLIENT_CREDENTIALS } from '../endpointAuth';

const defaultFormData: FormData = {
  name: '',
  description: '',
  connection_type: 'REST',
  url: '',
  environment: 'development',
  config_source: 'manual',
  response_format: 'json',
  method: 'POST',
  endpoint_path: '',
  project_id: '',
  organization_id: '',
  auth_type: ENDPOINT_AUTH_TYPES.BEARER_TOKEN,
  auth_token: '',
  client_credentials: EMPTY_CLIENT_CREDENTIALS,
  request_headers: '{}',
  disable_tracing: false,
  timeout_seconds: '',
};

const connectionProps = {
  onAutoConfigureOpen: jest.fn(),
};

describe('TabConnection — quickest setup', () => {
  it('opens auto-configure from the banner', () => {
    const onAutoConfigureOpen = jest.fn();
    render(
      <TabConnection
        {...connectionProps}
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={onAutoConfigureOpen}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /auto-configure/i }));
    expect(onAutoConfigureOpen).toHaveBeenCalledTimes(1);
  });
});

describe('TabConnection — auth token fields', () => {
  it('renders the API token field', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={defaultFormData}
        onChange={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });

  it('token field is type=password by default', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={defaultFormData}
        onChange={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute(
      'type',
      'password'
    );
  });

  it('token field becomes type=text after clicking the visibility toggle', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={defaultFormData}
        onChange={jest.fn()}
      />
    );
    fireEvent.click(
      screen.getByRole('button', { name: /show|toggle|visibility/i })
    );
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute('type', 'text');
  });

  it('calls onChange with auth_token when token field changes', () => {
    const onChange = jest.fn();
    render(
      <TabConnection
        {...connectionProps}
        formData={{ ...defaultFormData, auth_token: '' }}
        onChange={onChange}
      />
    );
    fireEvent.click(
      screen.getByRole('button', { name: /show|toggle|visibility/i })
    );
    fireEvent.change(screen.getByLabelText(/api token/i), {
      target: { value: 'sk-test-token' },
    });
    expect(onChange).toHaveBeenCalledWith('auth_token', 'sk-test-token');
  });

  it('displays the current token value', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={{ ...defaultFormData, auth_token: 'sk-my-token' }}
        onChange={jest.fn()}
      />
    );
    fireEvent.click(
      screen.getByRole('button', { name: /show|toggle|visibility/i })
    );
    expect(screen.getByLabelText(/api token/i)).toHaveValue('sk-my-token');
  });
});

describe('TabConnection — client credentials', () => {
  const clientCredentialsForm: FormData = {
    ...defaultFormData,
    auth_type: ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS,
  };

  it('shows the OAuth fields and hides the API token', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={clientCredentialsForm}
        onChange={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/token url/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/client id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^client secret/i)).toHaveAttribute(
      'type',
      'password'
    );
    expect(screen.queryByLabelText(/api token/i)).not.toBeInTheDocument();
  });

  it('reports a field change as a new client_credentials draft', () => {
    const onChange = jest.fn();
    render(
      <TabConnection
        {...connectionProps}
        formData={clientCredentialsForm}
        onChange={onChange}
      />
    );
    fireEvent.change(screen.getByLabelText(/client id/i), {
      target: { value: 'my-client' },
    });
    expect(onChange).toHaveBeenCalledWith('client_credentials', {
      ...EMPTY_CLIENT_CREDENTIALS,
      client_id: 'my-client',
    });
  });

  it('flags an invalid token URL', () => {
    render(
      <TabConnection
        {...connectionProps}
        formData={{
          ...clientCredentialsForm,
          client_credentials: {
            ...EMPTY_CLIENT_CREDENTIALS,
            token_url: 'not a url',
          },
        }}
        onChange={jest.fn()}
      />
    );
    expect(screen.getByText('Enter a valid URL')).toBeInTheDocument();
  });
});
