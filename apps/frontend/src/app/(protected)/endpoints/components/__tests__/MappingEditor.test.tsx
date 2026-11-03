import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

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

jest.mock('../RequestBodyEditor', () => ({
  __esModule: true,
  default: ({ value }: { value: string }) => (
    <pre data-testid="request-body">{value}</pre>
  ),
}));

import MappingEditor from '../MappingEditor';

// A template like the one that failed in the field: input has to be JSON.
const FROMJSON_TEMPLATE = '{\n  "payload": "{{ input | fromjson }}"\n}';

function renderEditor(
  overrides: Partial<React.ComponentProps<typeof MappingEditor>> = {}
) {
  const props = {
    requestTemplate: FROMJSON_TEMPLATE,
    responseMapping: {},
    onRequestTemplateChange: jest.fn(),
    onResponseMappingChange: jest.fn(),
    onTest: jest.fn(),
    testResponse: '',
    isTestingEndpoint: false,
    ...overrides,
  };
  render(<MappingEditor {...props} />);
  return props;
}

const responseJsonLink = () =>
  screen.getAllByRole('button', { name: 'Edit as JSON' }).at(-1) as HTMLElement;

describe('MappingEditor', () => {
  it('sends the typed test value on Check connection', async () => {
    const user = userEvent.setup({ delay: null });
    const { onTest } = renderEditor();

    fireEvent.change(screen.getByLabelText('Value for input'), {
      target: { value: '{"question": "What is my balance?"}' },
    });
    await user.click(screen.getByRole('button', { name: /check connection/i }));

    expect(onTest).toHaveBeenCalledWith({
      input: '{"question": "What is my balance?"}',
    });
  });

  it('lets the response mapping be typed without a test response', async () => {
    const user = userEvent.setup({ delay: null });
    const { onResponseMappingChange } = renderEditor();

    await user.click(responseJsonLink());
    fireEvent.change(screen.getByTestId('mock-editor'), {
      target: { value: '{"output": "$.data.reply"}' },
    });

    expect(onResponseMappingChange).toHaveBeenLastCalledWith({
      output: '$.data.reply',
    });
  });

  it('keeps the last valid mapping while the JSON is mid-edit', async () => {
    const user = userEvent.setup({ delay: null });
    const { onResponseMappingChange } = renderEditor({
      responseMapping: { output: '$.answer' },
    });

    await user.click(responseJsonLink());
    expect(screen.getByTestId('mock-editor')).toHaveValue(
      JSON.stringify({ output: '$.answer' }, null, 2)
    );
    fireEvent.change(screen.getByTestId('mock-editor'), {
      target: { value: '{"output": ' },
    });

    expect(onResponseMappingChange).not.toHaveBeenCalled();
    expect(
      screen.getByText(/JSON object whose values are all JSONPath strings/)
    ).toBeInTheDocument();
  });
});
