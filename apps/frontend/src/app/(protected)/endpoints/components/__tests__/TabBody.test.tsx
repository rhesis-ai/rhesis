import React from 'react';
import { act, render, screen, fireEvent, within } from '@testing-library/react';
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
  resultIsCurrent: false,
};

describe('TabMapping', () => {
  afterEach(() => jest.useRealTimers());

  it('shows the request template as one row per variable', () => {
    render(<TabMapping {...defaultProps} />);
    expect(screen.getByLabelText('API field for input')).toHaveValue('prompt');
    expect(screen.getByLabelText('API field for messages')).toHaveValue('');
  });

  it('writes a nested field path into the request template', () => {
    const onReqBodyChange = jest.fn();
    render(
      <TabMapping
        {...defaultProps}
        reqBody="{}"
        onReqBodyChange={onReqBodyChange}
      />
    );
    fireEvent.change(screen.getByLabelText('API field for messages'), {
      target: { value: 'payload.history' },
    });
    expect(JSON.parse(onReqBodyChange.mock.calls[0][0])).toEqual({
      payload: { history: '{{ messages | tojson }}' },
    });
  });

  it('blocks the test until input is mapped', () => {
    jest.useFakeTimers();
    const onRunTest = jest.fn();
    render(<TabMapping {...defaultProps} reqBody="{}" onRunTest={onRunTest} />);
    act(() => jest.advanceTimersByTime(2000));
    expect(onRunTest).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: /send test request/i })
    ).toBeDisabled();
  });

  it('runs the mapping test by itself once input is mapped', () => {
    jest.useFakeTimers();
    const onRunTest = jest.fn();
    render(<TabMapping {...defaultProps} onRunTest={onRunTest} />);
    expect(onRunTest).not.toHaveBeenCalled();
    act(() => jest.advanceTimersByTime(1000));
    expect(onRunTest).toHaveBeenCalledWith({ input: 'Hello, how are you?' });
  });

  it('keeps a current result instead of running again', () => {
    jest.useFakeTimers();
    const onRunTest = jest.fn();
    render(
      <TabMapping
        {...defaultProps}
        onRunTest={onRunTest}
        resultIsCurrent
        testResult={{ success: true, response: { raw_response: {} } }}
      />
    );
    act(() => jest.advanceTimersByTime(2000));
    expect(onRunTest).not.toHaveBeenCalled();
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

  it('offers the response keys for each Rhesis variable', () => {
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
    expect(
      screen.getByLabelText('Response value for output')
    ).toHaveTextContent('$.text');

    fireEvent.mouseDown(screen.getByLabelText('Response value for context'));
    expect(
      screen.getByRole('option', { name: '$.usage.tokens' })
    ).toBeInTheDocument();
  });
});
