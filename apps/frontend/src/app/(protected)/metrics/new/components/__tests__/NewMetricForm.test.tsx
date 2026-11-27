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
      { id: 'mt-rule', type_name: 'MetricType', type_value: 'rule' },
      { id: 'bt-1', type_name: 'BackendType', type_value: 'custom' },
      { id: 'bt-rhesis', type_name: 'BackendType', type_value: 'rhesis' },
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

describe('NewMetricForm rule', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCreateMetric.mockResolvedValue({ id: 'metric-1' });
  });

  function nameIt() {
    fireEvent.change(screen.getByRole('textbox', { name: /^Name/ }), {
      target: { value: 'Response time' },
    });
  }

  it('shows rule settings instead of a prompt and model', () => {
    render(<NewMetricForm type="rule" initialModels={[]} />);

    expect(screen.getByRole('radio', { name: 'Field rule' })).toBeVisible();
    expect(
      screen.queryByLabelText(/Evaluation Prompt/)
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Evaluation Model/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Threshold Value/)).not.toBeInTheDocument();
    expect(
      screen.getByText('Passes when duration_ms <= 5000.')
    ).toBeInTheDocument();
  });

  it('posts a field rule with its config, target and statement', async () => {
    render(<NewMetricForm type="rule" initialModels={[]} />);
    nameIt();
    const payload = await submit();

    expect(payload).toMatchObject({
      name: 'Response time',
      class_name: 'FieldRule',
      metric_type_id: 'mt-rule',
      backend_type_id: 'bt-rhesis',
      score_type: 'numeric',
      min_score: 0,
      max_score: 1,
      threshold: 1,
      threshold_operator: '>=',
      evaluation_prompt: 'duration_ms <= 5000',
      config: {
        field: 'duration_ms',
        op: '<=',
        value: 5000,
        target: { on: 'turn' },
      },
    });
    expect(payload).not.toHaveProperty('model_id');
  });

  it('refuses a comparison with a value that is not a number', async () => {
    render(<NewMetricForm type="rule" initialModels={[]} />);
    nameIt();
    fireEvent.change(screen.getByLabelText('Value'), {
      target: { value: 'fast' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a number');
    expect(mockCreateMetric).not.toHaveBeenCalled();
  });

  it('limits a response rule to targets with an expected response', async () => {
    render(<NewMetricForm type="rule" initialModels={[]} />);
    const targets = screen.getByRole('radiogroup', { name: 'Target' });
    fireEvent.click(
      within(targets).getByRole('radio', { name: 'Each tool call' })
    );

    fireEvent.click(screen.getByRole('radio', { name: 'Response rule' }));

    expect(
      within(targets).queryByRole('radio', { name: 'Each tool call' })
    ).not.toBeInTheDocument();
    expect(
      within(targets).queryByRole('radio', { name: 'The conversation' })
    ).not.toBeInTheDocument();
    expect(
      within(targets).getByRole('radio', { name: 'Each turn' })
    ).toHaveAttribute('aria-checked', 'true');

    nameIt();
    const payload = await submit();
    expect(payload).toMatchObject({
      class_name: 'ResponseRule',
      config: { match: 'exact', target: { on: 'turn' } },
    });
  });
});
