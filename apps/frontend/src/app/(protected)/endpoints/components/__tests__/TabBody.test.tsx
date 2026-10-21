import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@/config/runtime-config', () => ({
  publicEnv: () => ({ architectHelpArticleUrls: [] }),
}));

import TabMapping from '../TabMapping';

const defaultProps = {
  reqBody: '{\n  "prompt": "{{ input }}"\n}',
  resBody: '{}',
  onReqBodyChange: jest.fn(),
  onResBodyChange: jest.fn(),
  testResult: null,
  isTestingEndpoint: false,
  onRunTest: jest.fn(),
};

describe('TabMapping', () => {
  it('shows the request template as one row per variable', () => {
    render(<TabMapping {...defaultProps} />);
    expect(screen.getByLabelText('API field for input')).toHaveValue('prompt');
    expect(screen.getByLabelText('API field for messages')).toHaveValue('');
  });

  it('writes a typed field name into the request template', () => {
    const onReqBodyChange = jest.fn();
    render(
      <TabMapping
        {...defaultProps}
        reqBody="{}"
        onReqBodyChange={onReqBodyChange}
      />
    );
    fireEvent.change(screen.getByLabelText('API field for messages'), {
      target: { value: 'history' },
    });
    expect(JSON.parse(onReqBodyChange.mock.calls[0][0])).toEqual({
      history: '{{ messages | tojson }}',
    });
  });

  it('blocks the test until input is mapped', () => {
    render(<TabMapping {...defaultProps} reqBody="{}" />);
    expect(
      screen.getByRole('button', { name: /run test request/i })
    ).toBeDisabled();
  });

  it('runs the mapping test with a sample prompt', () => {
    const onRunTest = jest.fn();
    render(<TabMapping {...defaultProps} onRunTest={onRunTest} />);
    fireEvent.click(screen.getByRole('button', { name: /run test request/i }));
    expect(onRunTest).toHaveBeenCalledWith({ input: 'Hello, how are you?' });
  });

  it('shows the endpoint error when the test fails', () => {
    render(
      <TabMapping
        {...defaultProps}
        testResult={{
          success: false,
          status: 401,
          error: 'HTTP 401 error from endpoint: Unauthorized',
        }}
      />
    );
    const alert = screen.getByRole('alert');
    expect(
      within(alert).getByText('HTTP 401 error from endpoint')
    ).toBeInTheDocument();
    expect(within(alert).getByText('Unauthorized')).toBeInTheDocument();
  });

  it('lists the response keys once the test passes', () => {
    render(
      <TabMapping
        {...defaultProps}
        resBody='{"output": "$.text"}'
        testResult={{
          success: true,
          response: { raw_response: { text: 'hi', usage: { tokens: 3 } } },
        }}
      />
    );
    expect(screen.getByText('Test request successful')).toBeInTheDocument();
    expect(screen.getByText('$.text')).toBeInTheDocument();
    expect(screen.getByText('$.usage.tokens')).toBeInTheDocument();
    expect(screen.getByLabelText('Variable for $.text')).toHaveTextContent(
      'output'
    );
  });
});
