import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('../JsonPreview', () => ({
  JsonPreview: ({ value }: { value: unknown }) => (
    <div data-testid="json-preview">{JSON.stringify(value)}</div>
  ),
  TemplatePreview: ({ template }: { template: string }) => (
    <div data-testid="template-preview">{template}</div>
  ),
  responseMappingToPathToVar: (m: Record<string, string>) =>
    Object.fromEntries(Object.entries(m).map(([k, v]) => [v, k])),
}));

import TabTest from '../TabTest';

const defaultProps = {
  url: 'https://api.example.com/chat',
  method: 'POST',
  reqBody: '{"input": "{{ input }}"}',
  resBody: '{"output": "$.choices[0].message.content"}',
  requestHeaders: '{}',
  authToken: '',
  testResult: null,
  isTestingEndpoint: false,
  onRunTest: jest.fn(),
};

describe('TabTest', () => {
  it('renders the Check connection button', () => {
    render(<TabTest {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: /check connection/i })
    ).toBeInTheDocument();
  });

  it('shows "No response yet" placeholder before a test is run', () => {
    render(<TabTest {...defaultProps} />);
    expect(
      screen.getAllByText(/run a test to see the response/i).length
    ).toBeGreaterThan(0);
  });

  it('extracts template variables from reqBody and shows input fields', () => {
    render(<TabTest {...defaultProps} />);
    expect(screen.getByText('{{ input }}')).toBeInTheDocument();
  });

  it('shows "No template variables" message when reqBody has no variables', () => {
    render(<TabTest {...defaultProps} reqBody='{"static": "value"}' />);
    expect(
      screen.getByText(/no template variables in request body/i)
    ).toBeInTheDocument();
  });

  it('calls onRunTest when Check connection is clicked', () => {
    const onRunTest = jest.fn();
    render(<TabTest {...defaultProps} onRunTest={onRunTest} />);
    fireEvent.click(screen.getByRole('button', { name: /check connection/i }));
    expect(onRunTest).toHaveBeenCalledTimes(1);
  });

  it('shows error alert when testResult has an error', () => {
    render(
      <TabTest
        {...defaultProps}
        testResult={{ success: false, error: 'Connection refused' }}
      />
    );
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('shows status code after a successful test', () => {
    render(
      <TabTest
        {...defaultProps}
        testResult={{
          success: true,
          response: { status_code: 200, raw_response: { output: 'hello' } },
        }}
      />
    );
    expect(screen.getByText('200')).toBeInTheDocument();
  });

  it('shows the URL in the request panel', () => {
    render(<TabTest {...defaultProps} />);
    expect(
      screen.getAllByText(/https:\/\/api\.example\.com\/chat/).length
    ).toBeGreaterThan(0);
  });

  it('shows "No response mapping configured yet" when resBody is empty object', () => {
    render(<TabTest {...defaultProps} resBody="{}" />);
    expect(
      screen.getByText(/no response mapping configured yet/i)
    ).toBeInTheDocument();
  });
});
