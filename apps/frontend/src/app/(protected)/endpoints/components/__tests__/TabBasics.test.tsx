import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import TabBasics from '../tabs/TabBasics';
import type { FormData } from '../EndpointForm';
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
  auth_token: '',
  request_headers: '{}',
  disable_tracing: false,
};

const projects = [
  { id: 'proj-1', name: 'Alpha', description: 'First' },
  { id: 'proj-2', name: 'Beta', description: 'Second' },
] as unknown as Project[];

describe('TabBasics', () => {
  it('renders required text fields', () => {
    render(
      <TabBasics
        formData={defaultFormData}
        onChange={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    expect(screen.getByRole('textbox', { name: /method/i })).toHaveValue(
      'POST'
    );
    expect(
      screen.getByRole('textbox', { name: /endpoint url/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /endpoint name/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /description/i })
    ).toBeInTheDocument();
  });

  it('hides the project dropdown when hideProjectSelect is true', () => {
    render(
      <TabBasics
        formData={defaultFormData}
        onChange={jest.fn()}
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
      <TabBasics
        formData={defaultFormData}
        onChange={jest.fn()}
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
      <TabBasics
        formData={defaultFormData}
        onChange={jest.fn()}
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
      <TabBasics
        formData={defaultFormData}
        onChange={jest.fn()}
        projects={[]}
        loadingProjects={false}
      />
    );
    expect(screen.getByText(/no projects available/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /create project/i })
    ).toBeInTheDocument();
  });

  it('shows URL validation error for malformed URL', () => {
    render(
      <TabBasics
        formData={{ ...defaultFormData, url: 'not-a-url' }}
        onChange={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    expect(screen.getByText(/enter a valid url/i)).toBeInTheDocument();
  });

  it('does not show URL error for valid URL', () => {
    render(
      <TabBasics
        formData={{ ...defaultFormData, url: 'https://api.example.com' }}
        onChange={jest.fn()}
        projects={projects}
        loadingProjects={false}
      />
    );
    expect(screen.queryByText(/enter a valid url/i)).not.toBeInTheDocument();
  });

  it('calls onChange with name when endpoint name field changes', () => {
    const onChange = jest.fn();
    render(
      <TabBasics
        formData={defaultFormData}
        onChange={onChange}
        projects={projects}
        loadingProjects={false}
      />
    );
    fireEvent.change(screen.getByRole('textbox', { name: /endpoint name/i }), {
      target: { value: 'My API' },
    });
    expect(onChange).toHaveBeenCalledWith('name', 'My API');
  });

  it('calls onChange with url when URL field changes', () => {
    const onChange = jest.fn();
    render(
      <TabBasics
        formData={defaultFormData}
        onChange={onChange}
        projects={projects}
        loadingProjects={false}
      />
    );
    fireEvent.change(screen.getByRole('textbox', { name: /endpoint url/i }), {
      target: { value: 'https://api.example.com' },
    });
    expect(onChange).toHaveBeenCalledWith('url', 'https://api.example.com');
  });

  it('calls onChange with description when description field changes', () => {
    const onChange = jest.fn();
    render(
      <TabBasics
        formData={defaultFormData}
        onChange={onChange}
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
});
