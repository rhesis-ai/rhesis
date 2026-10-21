import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import TabOverview from '../TabOverview';
import type { FormData } from '../EndpointForm';
import { ENDPOINT_AUTH_TYPES } from '@/constants/endpoint-auth';
import { EMPTY_CLIENT_CREDENTIALS } from '../endpointAuth';
import type { Project } from '@/utils/api-client/interfaces/project';

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

const projects = [
  { id: 'proj-1', name: 'Alpha', description: 'First' },
  { id: 'proj-2', name: 'Beta', description: 'Second' },
] as unknown as Project[];

describe('TabOverview', () => {
  it('renders required text fields', () => {
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    expect(
      screen.getByRole('textbox', { name: /endpoint name/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /description/i })
    ).toBeInTheDocument();
  });

  it('hides the project dropdown when hideProjectSelect is true', () => {
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
        hideProjectSelect
      />
    );
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /endpoint name/i })
    ).toBeInTheDocument();
  });

  it('shows a warning when hideProjectSelect is true but no project is resolved', () => {
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
        hideProjectSelect
      />
    );
    expect(screen.getByText(/no active project selected/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /select project/i })
    ).toHaveAttribute('href', '/projects');
  });

  it('disables the project dropdown while projects are loading', () => {
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={jest.fn()}
        projects={[]}
        loadingProjects={true}
      />
    );
    expect(screen.getByRole('combobox')).toHaveAttribute(
      'aria-disabled',
      'true'
    );
  });

  it('shows no-projects warning when list is empty and not loading', () => {
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={jest.fn()}
        projects={[]}
        loadingProjects={false}
      />
    );
    expect(screen.getByText(/no projects available/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /create project/i })
    ).toBeInTheDocument();
  });

  it('calls onChange with name when endpoint name field changes', () => {
    const onChange = jest.fn();
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={onChange}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    fireEvent.change(screen.getByRole('textbox', { name: /endpoint name/i }), {
      target: { value: 'My API' },
    });
    expect(onChange).toHaveBeenCalledWith('name', 'My API');
  });

  it('calls onChange with description when description field changes', () => {
    const onChange = jest.fn();
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={onChange}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    fireEvent.change(screen.getByRole('textbox', { name: /description/i }), {
      target: { value: 'My endpoint description' },
    });
    expect(onChange).toHaveBeenCalledWith(
      'description',
      'My endpoint description'
    );
  });

  it('shows tracing as enabled and turning it off sets disable_tracing', () => {
    const onChange = jest.fn();
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={onChange}
        onAutoConfigureOpen={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    const toggle = screen.getByRole('switch', { name: /enable tracing/i });
    expect(toggle).toBeChecked();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith('disable_tracing', true);
  });

  it('opens auto-configure from the quickest setup banner', () => {
    const onAutoConfigureOpen = jest.fn();
    render(
      <TabOverview
        formData={defaultFormData}
        onChange={jest.fn()}
        onAutoConfigureOpen={onAutoConfigureOpen}
        projects={projects}
        loadingProjects={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /auto-configure/i }));
    expect(onAutoConfigureOpen).toHaveBeenCalledTimes(1);
  });
});
