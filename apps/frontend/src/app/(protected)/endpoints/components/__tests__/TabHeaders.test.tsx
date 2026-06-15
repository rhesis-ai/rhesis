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

import TabHeaders from '../tabs/TabHeaders';
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

describe('TabHeaders', () => {
  it('renders the API token field', () => {
    render(
      <TabHeaders
        formData={defaultFormData}
        onChange={jest.fn()}
        showAuthToken={false}
        onToggleAuthToken={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });

  it('token field is type=password by default', () => {
    render(
      <TabHeaders
        formData={defaultFormData}
        onChange={jest.fn()}
        showAuthToken={false}
        onToggleAuthToken={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute(
      'type',
      'password'
    );
  });

  it('token field is type=text when showAuthToken is true', () => {
    render(
      <TabHeaders
        formData={defaultFormData}
        onChange={jest.fn()}
        showAuthToken={true}
        onToggleAuthToken={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toHaveAttribute('type', 'text');
  });

  it('calls onToggleAuthToken when the visibility button is clicked', () => {
    const onToggle = jest.fn();
    render(
      <TabHeaders
        formData={defaultFormData}
        onChange={jest.fn()}
        showAuthToken={false}
        onToggleAuthToken={onToggle}
      />
    );
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('calls onChange with auth_token when token field changes', () => {
    const onChange = jest.fn();
    render(
      <TabHeaders
        formData={defaultFormData}
        onChange={onChange}
        showAuthToken={true}
        onToggleAuthToken={jest.fn()}
      />
    );
    fireEvent.change(screen.getByLabelText(/api token/i), {
      target: { value: 'sk-test-token' },
    });
    expect(onChange).toHaveBeenCalledWith('auth_token', 'sk-test-token');
  });

  it('displays the current token value', () => {
    render(
      <TabHeaders
        formData={{ ...defaultFormData, auth_token: 'sk-my-token' }}
        onChange={jest.fn()}
        showAuthToken={true}
        onToggleAuthToken={jest.fn()}
      />
    );
    expect(screen.getByLabelText(/api token/i)).toHaveValue('sk-my-token');
  });
});
