import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@/config/runtime-config', () => ({
  publicEnv: () => ({ architectHelpArticleUrls: [] }),
}));

import TabTest from '../TabTest';

const defaultProps = {
  url: 'https://api.example.com/chat',
  method: 'POST',
  reqBody:
    '{"prompt": "{{ input }}", "history": "{{ messages | tojson }}", "run": "{{ test_run_id }}"}',
  resBody: '{"output": "$.text"}',
  requestHeaders: '{}',
  testResult: null,
  isTestingEndpoint: false,
  onRunTest: jest.fn(),
};

describe('TabTest', () => {
  it('asks for a value per variable, skipping ones Rhesis fills in', () => {
    render(<TabTest {...defaultProps} />);
    expect(screen.getByLabelText('Value for input')).toBeInTheDocument();
    expect(screen.getByLabelText('Value for messages')).toBeInTheDocument();
    expect(
      screen.queryByLabelText('Value for test_run_id')
    ).not.toBeInTheDocument();
  });

  it('blocks the test until input has a value', () => {
    render(<TabTest {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: /run test request/i })
    ).toBeDisabled();
  });

  it('sends typed messages as a single user turn', async () => {
    const onRunTest = jest.fn();
    render(<TabTest {...defaultProps} onRunTest={onRunTest} />);
    fireEvent.change(screen.getByLabelText('Value for input'), {
      target: { value: 'Hi' },
    });
    fireEvent.change(screen.getByLabelText('Value for messages'), {
      target: { value: 'Earlier question' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run test request/i }));
    await Promise.resolve();
    expect(onRunTest).toHaveBeenCalledWith({
      input: 'Hi',
      messages: [{ role: 'user', content: 'Earlier question' }],
    });
  });

  it('shows the returned value for each mapped variable', () => {
    render(
      <TabTest
        {...defaultProps}
        testResult={{
          success: true,
          response: { raw_response: { text: 'Hello back' } },
        }}
      />
    );
    expect(screen.getByText('Endpoint is ready')).toBeInTheDocument();
    expect(screen.getByText('Hello back')).toBeInTheDocument();
  });

  it('shows the error when the test fails', () => {
    render(
      <TabTest
        {...defaultProps}
        testResult={{ success: false, error: 'Connection refused' }}
      />
    );
    expect(screen.getByText('Test request failed')).toBeInTheDocument();
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });
});
