import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import AutoConfigureModal from '../AutoConfigureModal';

// Mock Monaco Editor
jest.mock('@monaco-editor/react', () => {
  const MockEditor = ({
    value,
    onChange,
    options,
  }: {
    value?: string;
    onChange?: (value: string) => void;
    options?: { readOnly?: boolean; placeholder?: string };
  }) => (
    <textarea
      data-testid="mock-editor"
      value={value || ''}
      onChange={e => onChange?.(e.target.value)}
      readOnly={options?.readOnly}
      placeholder={options?.placeholder}
    />
  );
  return { __esModule: true, default: MockEditor };
});

// Mock the server action
const mockAutoConfigure = jest.fn();
jest.mock('@/actions/endpoints/auto-configure', () => ({
  autoConfigureEndpoint: (...args: unknown[]) => mockAutoConfigure(...args),
}));

const SUCCESS_RESULT = {
  status: 'success' as const,
  request_mapping: { query: '{{ input }}' },
  response_mapping: { output: '$.response' },
  request_headers: { 'Content-Type': 'application/json' },
  url: 'https://api.example.com',
  method: 'POST',
  conversation_mode: 'single_turn' as const,
  confidence: 0.85,
  reasoning: 'Detected API pattern',
  warnings: [] as string[],
  probe_success: true,
  probe_attempts: 1,
};

const PARTIAL_RESULT = {
  ...SUCCESS_RESULT,
  status: 'partial' as const,
  confidence: 0.4,
  warnings: ['Mapping generated but could not be verified via endpoint probe.'],
  probe_success: false,
  probe_error: 'HTTP 422: validation error',
};

const _FAILED_RESULT = {
  status: 'failed' as const,
  error: 'Could not parse the input',
  confidence: 0,
  reasoning: 'The AI could not identify an API structure',
  method: 'POST',
  conversation_mode: 'single_turn' as const,
  warnings: [] as string[],
  probe_success: false,
  probe_attempts: 0,
};

describe('AutoConfigureModal', () => {
  const defaultProps = {
    open: true,
    onClose: jest.fn(),
    onApply: jest.fn(),
    url: 'https://api.example.com',
    authToken: 'test-token',
    method: 'POST',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders modal when open=true', () => {
    render(<AutoConfigureModal {...defaultProps} />);

    expect(screen.getByText('Auto-configure Endpoint')).toBeInTheDocument();
    expect(
      screen.getByText(/paste anything about your endpoint/i)
    ).toBeInTheDocument();
  });

  it('does not render when open=false', () => {
    render(<AutoConfigureModal {...defaultProps} open={false} />);

    expect(
      screen.queryByText('Auto-configure Endpoint')
    ).not.toBeInTheDocument();
  });

  it('shows paste area with helper text', () => {
    render(<AutoConfigureModal {...defaultProps} />);

    expect(
      screen.getByText(/paste a curl command, python code/i)
    ).toBeInTheDocument();
  });

  it('auto-configure button is disabled when text area is empty', () => {
    render(<AutoConfigureModal {...defaultProps} />);

    const button = screen.getByRole('button', { name: /auto-configure/i });
    expect(button).toBeDisabled();
  });

  it('auto-configure button is enabled when text is entered', async () => {
    const user = userEvent.setup();
    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    const textArea = editors[0];
    await user.type(textArea, 'curl -X POST https://api.example.com');

    const button = screen.getByRole('button', { name: /auto-configure/i });
    expect(button).not.toBeDisabled();
  });

  it('calls server action on auto-configure click', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: true,
      data: SUCCESS_RESULT,
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'curl -X POST https://api.example.com');

    const button = screen.getByRole('button', { name: /auto-configure/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockAutoConfigure).toHaveBeenCalledWith({
        input_text: 'curl -X POST https://api.example.com',
        url: 'https://api.example.com',
        auth_token: 'test-token',
        method: 'POST',
        probe: true,
      });
    });
  });

  it('displays success results with Apply button', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: true,
      data: SUCCESS_RESULT,
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'some code');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(screen.getByText(/confidence: high/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /apply to endpoint/i })
      ).toBeInTheDocument();
    });
  });

  it('displays partial results with Apply Anyway button', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: true,
      data: PARTIAL_RESULT,
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'some code');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /apply anyway/i })
      ).toBeInTheDocument();
    });
  });

  it('displays failure with error message', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: false,
      error: 'Auto-configure failed',
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'garbled text');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(screen.getByText(/auto-configure failed/i)).toBeInTheDocument();
    });
  });

  it('displays probe error details', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: true,
      data: PARTIAL_RESULT,
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'some code');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/HTTP 422: validation error/i)
      ).toBeInTheDocument();
    });
  });

  it('calls onApply with result when Apply is clicked', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: true,
      data: SUCCESS_RESULT,
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'some code');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /apply to endpoint/i })
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole('button', { name: /apply to endpoint/i })
    );
    expect(defaultProps.onApply).toHaveBeenCalledWith(SUCCESS_RESULT);
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<AutoConfigureModal {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('retains input text after failure', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: false,
      error: 'Failed',
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'my curl command');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument();
    });

    // The text area should still have the input
    expect(editors[0]).toHaveValue('my curl command');
  });

  it('shows retry button after first attempt', async () => {
    const user = userEvent.setup();
    mockAutoConfigure.mockResolvedValue({
      success: false,
      error: 'Failed',
    });

    render(<AutoConfigureModal {...defaultProps} />);

    const editors = screen.getAllByTestId('mock-editor');
    await user.type(editors[0], 'some code');
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /retry/i })
      ).toBeInTheDocument();
    });
  });
});
