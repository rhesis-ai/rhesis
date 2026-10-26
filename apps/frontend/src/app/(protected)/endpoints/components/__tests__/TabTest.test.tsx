import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

import TabTest from '../TabTest';
import type { TestValues } from '../testValues';

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

type Props = Omit<
  React.ComponentProps<typeof TabTest>,
  'values' | 'onValuesChange'
> & { values?: TestValues };

// The wizard owns the test values; hold them here so typing updates the fields.
function WithTabTestValues({ values: initial, ...props }: Props) {
  const [values, setValues] = useState<TestValues>(initial ?? {});
  return <TabTest {...props} values={values} onValuesChange={setValues} />;
}

describe('TabTest', () => {
  it('asks for a value per variable, skipping ones Rhesis fills in', () => {
    render(<WithTabTestValues {...defaultProps} />);
    expect(screen.getByLabelText('Value for input')).toBeInTheDocument();
    expect(screen.getByLabelText('Value for messages')).toBeInTheDocument();
    expect(
      screen.queryByLabelText('Value for test_run_id')
    ).not.toBeInTheDocument();
  });

  it('blocks the test until input has a value', () => {
    render(<WithTabTestValues {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: /send test request/i })
    ).toBeDisabled();
  });

  it('sends typed messages as a single user turn', async () => {
    const onRunTest = jest.fn();
    render(<WithTabTestValues {...defaultProps} onRunTest={onRunTest} />);
    fireEvent.change(screen.getByLabelText('Value for input'), {
      target: { value: 'Hi' },
    });
    fireEvent.change(screen.getByLabelText('Value for messages'), {
      target: { value: 'Earlier question' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send test request/i }));
    await Promise.resolve();
    expect(onRunTest).toHaveBeenCalledWith({
      input: 'Hi',
      messages: [{ role: 'user', content: 'Earlier question' }],
    });
  });

  it('shows the returned value for each mapped variable', () => {
    render(
      <WithTabTestValues
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

  it('labels returned values by variable name and shows JSON as JSON', () => {
    render(
      <WithTabTestValues
        {...defaultProps}
        resBody='{"output": "$.text", "metadata": "$.meta"}'
        testResult={{
          success: true,
          response: {
            raw_response: { text: 'Hi', meta: { model: 'gpt-x', tokens: 12 } },
          },
        }}
      />
    );
    expect(screen.getByText('metadata')).toBeInTheDocument();
    expect(screen.queryByText('Metadata')).not.toBeInTheDocument();
    // Rendered as a JSON tree, not one stringified line.
    expect(
      screen.queryByText('{"model":"gpt-x","tokens":12}')
    ).not.toBeInTheDocument();
    expect(screen.getAllByText(/gpt-x/).length).toBeGreaterThan(0);
  });

  it('shows the error when the test fails', () => {
    render(
      <WithTabTestValues
        {...defaultProps}
        testResult={{ success: false, error: 'Connection refused' }}
      />
    );
    expect(screen.getByText('Test request failed')).toBeInTheDocument();
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('says creating without a passing test is still possible', () => {
    render(<WithTabTestValues {...defaultProps} />);
    expect(screen.getByText(/no successful test yet/i)).toBeInTheDocument();
  });

  it('starts from the values typed in the Mapping step', () => {
    render(
      <WithTabTestValues {...defaultProps} values={{ input: 'From mapping' }} />
    );
    expect(screen.getByLabelText('Value for input')).toHaveValue(
      'From mapping'
    );
  });

  it('reloads the JSON when the Mapping step changes the shared values', async () => {
    const onValuesChange = jest.fn();
    const props = { ...defaultProps, onValuesChange };
    const { rerender } = render(
      <TabTest {...props} values={{ input: 'Old' }} />
    );
    fireEvent.click(screen.getByText('Edit as JSON'));
    const editor = (await screen.findByTestId(
      'mock-editor'
    )) as HTMLTextAreaElement;
    expect(JSON.parse(editor.value).input).toBe('Old');

    rerender(<TabTest {...props} values={{ input: 'From mapping' }} />);
    expect(JSON.parse(editor.value).input).toBe('From mapping');
  });

  it('keeps what is being typed in the JSON editor', async () => {
    render(<WithTabTestValues {...defaultProps} values={{ input: 'Hi' }} />);
    fireEvent.click(screen.getByText('Edit as JSON'));
    const editor = await screen.findByTestId('mock-editor');
    const typed = '{\n  "input": "Typed",\n  "messages": ""\n}';
    fireEvent.change(editor, { target: { value: typed } });
    expect(editor).toHaveValue(typed);
  });
});
