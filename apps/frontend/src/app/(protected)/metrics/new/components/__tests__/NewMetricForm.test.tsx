import React from 'react';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
  act,
} from '@testing-library/react';
import '@testing-library/jest-dom';
import NewMetricForm from '../NewMetricForm';

const mockCreateMetric = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/metrics/new',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricsClient: () => ({ createMetric: mockCreateMetric }),
    getTagsClient: () => ({ assignTagToEntity: jest.fn() }),
    getModelsClient: () => ({ getModels: jest.fn() }),
  })),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/hooks/useLookups', () => ({
  useTypeLookups: () => ({
    data: [
      { id: 'mt-1', type_name: 'MetricType', type_value: 'custom-prompt' },
      { id: 'bt-1', type_name: 'BackendType', type_value: 'custom' },
    ],
  }),
  useMetricTargets: () => ({
    data: [
      {
        on: 'turn',
        label: 'Each turn',
        description: 'Each exchange.',
        per_span: false,
      },
      {
        on: 'conversation',
        label: 'The conversation',
        description: 'The whole conversation.',
        per_span: false,
      },
      {
        on: 'tool_call',
        label: 'Each tool call',
        description: 'Each tool call.',
        per_span: true,
      },
    ],
  }),
}));

function fillRequiredFields() {
  fireEvent.change(screen.getByRole('textbox', { name: /^Name/ }), {
    target: { value: 'Helpfulness' },
  });
  fireEvent.change(screen.getByLabelText(/Evaluation Prompt/), {
    target: { value: 'Is it helpful?' },
  });
  fireEvent.change(screen.getByLabelText(/Minimum Score/), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText(/Maximum Score/), {
    target: { value: '10' },
  });
  fireEvent.change(screen.getByLabelText(/Threshold Value/), {
    target: { value: '5' },
  });
}

async function submit() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Create Metric' }));
  });
  await waitFor(() => expect(mockCreateMetric).toHaveBeenCalled());
  return mockCreateMetric.mock.calls[0][0];
}

describe('NewMetricForm target', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCreateMetric.mockResolvedValue({ id: 'metric-1' });
  });

  it('defaults to each turn', async () => {
    render(<NewMetricForm type="custom-prompt" initialModels={[]} />);

    expect(screen.getByRole('radio', { name: 'Each turn' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    fillRequiredFields();
    const payload = await submit();

    expect(payload.config).toEqual({ target: { on: 'turn' } });
    expect(payload).not.toHaveProperty('metric_scope');
  });

  it('asks for a name only for per-span targets and sends it', async () => {
    render(<NewMetricForm type="custom-prompt" initialModels={[]} />);
    const group = screen.getByRole('radiogroup');
    const picker = group.parentElement as HTMLElement;

    expect(within(picker).queryByLabelText('Name')).not.toBeInTheDocument();

    fillRequiredFields();
    fireEvent.click(screen.getByRole('radio', { name: 'Each tool call' }));
    fireEvent.change(within(picker).getByLabelText('Name'), {
      target: { value: ' search ' },
    });
    const payload = await submit();

    expect(payload.config).toEqual({
      target: { on: 'tool_call', name: 'search' },
    });
  });

  it('drops the name when switching back to a whole-test target', async () => {
    render(<NewMetricForm type="custom-prompt" initialModels={[]} />);
    const picker = screen.getByRole('radiogroup').parentElement as HTMLElement;

    fireEvent.click(screen.getByRole('radio', { name: 'Each tool call' }));
    fireEvent.change(within(picker).getByLabelText('Name'), {
      target: { value: 'search' },
    });
    fireEvent.click(screen.getByRole('radio', { name: 'The conversation' }));
    fillRequiredFields();
    const payload = await submit();

    expect(payload.config).toEqual({ target: { on: 'conversation' } });
  });
});
