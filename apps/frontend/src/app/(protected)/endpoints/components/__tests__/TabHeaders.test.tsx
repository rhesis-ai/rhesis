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
  auth_token: '',
  request_headers: '{}',
  disable_tracing: false,
};

describe('TabConnection — auth token fields', () => {
  it('renders the API token field', () => {
    render(<TabConnection formData={defaultFormData} onChange={jest.fn()} />);
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });

  it('token field is type=password by default', () => {
    render(<TabConnection formData={defaultFormData} onChange={jest.fn()} />);
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute(
      'type',
      'password'
    );
  });

  it('token field becomes type=text after clicking the visibility toggle', () => {
    render(<TabConnection formData={defaultFormData} onChange={jest.fn()} />);
    fireEvent.click(
      screen.getByRole('button', { name: /show|toggle|visibility/i })
    );
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute('type', 'text');
  });

  it('calls onChange with auth_token when token field changes', () => {
    const onChange = jest.fn();
    render(
      <TabConnection
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
