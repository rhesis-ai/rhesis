import React, { useState } from 'react';
import { act, render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@/config/runtime-config', () => ({
  publicEnv: () => ({ architectHelpArticleUrls: [] }),
}));

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

import TabMapping from '../TabMapping';
import { DEFAULT_TEST_VALUES, type TestValues } from '../testValues';

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

type Props = Omit<
  React.ComponentProps<typeof TabMapping>,
  'testValues' | 'onTestValuesChange'
> & { testValues?: TestValues };

// The wizard owns the test values; hold them here so typing updates the fields.
function WithTabMappingValues({ testValues: initial, ...props }: Props) {
  const [values, setValues] = useState<TestValues>(
    initial ?? DEFAULT_TEST_VALUES
  );
  return (
    <TabMapping {...props} testValues={values} onTestValuesChange={setValues} />
  );
}

describe('TabMapping', () => {
  afterEach(() => jest.useRealTimers());

  it('shows the request template as one row per variable', () => {
    render(<WithTabMappingValues {...defaultProps} />);
    expect(screen.getByLabelText('API field for input')).toHaveValue('prompt');
    expect(screen.getByLabelText('API field for messages')).toHaveValue('');
  });

  it('links to the mapping examples in the docs', () => {
    render(<WithTabMappingValues {...defaultProps} />);
    expect(
      screen.getByRole('link', { name: /see mapping examples/i })
    ).toHaveAttribute(
      'href',
      'https://docs.rhesis.ai/docs/endpoints/mapping-examples'
    );
  });

  it('writes a nested field path into the request template', () => {
    const onReqBodyChange = jest.fn();
    render(
      <WithTabMappingValues
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
    render(
      <WithTabMappingValues
        {...defaultProps}
        reqBody="{}"
        onRunTest={onRunTest}
      />
    );
    act(() => jest.advanceTimersByTime(2000));
    expect(onRunTest).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: /send test request/i })
    ).toBeDisabled();
  });

  it('runs the mapping test by itself once input is mapped', () => {
    jest.useFakeTimers();
    const onRunTest = jest.fn();
    render(<WithTabMappingValues {...defaultProps} onRunTest={onRunTest} />);
    expect(onRunTest).not.toHaveBeenCalled();
    act(() => jest.advanceTimersByTime(1000));
    expect(onRunTest).toHaveBeenCalled();
  });

  it('hides the test request until asked for', () => {
    render(<WithTabMappingValues {...defaultProps} />);
    expect(screen.queryByText('Test request')).not.toBeInTheDocument();
  });

  // The editor loads lazily.
  const openTestRequest = async () => {
    fireEvent.click(
      screen.getByRole('button', { name: 'More test request options' })
    );
    fireEvent.click(
      screen.getByRole('menuitem', { name: 'Edit test request' })
    );
    return screen.findByTestId('mock-editor');
  };

  it('opens the test request as JSON, starting from a default input', async () => {
    render(<WithTabMappingValues {...defaultProps} />);
    const editor = await openTestRequest();
    expect(JSON.parse((editor as HTMLTextAreaElement).value)).toEqual({
      input: 'Hello, how are you?',
    });
    expect(screen.queryByText('Switch to easy input')).not.toBeInTheDocument();
  });

  it('closes the test request with the close button', async () => {
    render(<WithTabMappingValues {...defaultProps} />);
    await openTestRequest();
    fireEvent.click(screen.getByRole('button', { name: 'Hide test request' }));
    expect(screen.queryByText('Test request')).not.toBeInTheDocument();
  });

  it('lists every mapped variable, skipping ones Rhesis fills in', async () => {
    render(
      <WithTabMappingValues
        {...defaultProps}
        reqBody='{"prompt": "{{ input }}", "user": "{{ user_id }}", "run": "{{ test_run_id }}"}'
      />
    );
    const editor = await openTestRequest();
    expect(JSON.parse((editor as HTMLTextAreaElement).value)).toEqual({
      input: 'Hello, how are you?',
      user_id: '',
    });
  });

  it('passes JSON test values up to the wizard', async () => {
    const onTestValuesChange = jest.fn();
    render(
      <TabMapping
        {...defaultProps}
        testValues={{ input: 'Hello' }}
        onTestValuesChange={onTestValuesChange}
      />
    );
    fireEvent.change(await openTestRequest(), {
      target: { value: '{"input": "{\\"order_id\\": \\"A-1\\"}"}' },
    });
    expect(onTestValuesChange).toHaveBeenLastCalledWith({
      input: '{"order_id": "A-1"}',
    });
  });

  it('warns when input is not text, since test runs never send that', async () => {
    render(<WithTabMappingValues {...defaultProps} />);
    fireEvent.change(await openTestRequest(), {
      target: { value: '{"input": {"order_id": "A-1"}}' },
    });
    expect(
      screen.getByText(/test runs always send/i, { exact: false })
    ).toBeInTheDocument();
  });

  it('keeps a current result instead of running again', () => {
    jest.useFakeTimers();
    const onRunTest = jest.fn();
    render(
      <WithTabMappingValues
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
      <WithTabMappingValues
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
      <WithTabMappingValues
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
