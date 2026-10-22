import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useParams: () => ({}),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'test-token' },
    status: 'authenticated',
  }),
}));

jest.mock('@/config/runtime-config', () => ({
  publicEnv: () => ({ architectHelpArticleUrls: [] }),
}));

const mockNotificationsShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockNotificationsShow }),
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ markStepComplete: jest.fn() }),
}));

jest.mock('@/hooks/useQuotaGate', () => ({
  useQuotaGate: () => ({ exhausted: false, notice: null }),
}));

const mockCreateEndpoint = jest.fn();
jest.mock('@/hooks/useCreateEndpoint', () => ({
  useCreateEndpoint: () => mockCreateEndpoint,
}));

const mockTestEndpoint = jest.fn();
jest.mock('@/hooks/useEndpoints', () => ({
  useTestEndpoint: () => ({ mutateAsync: mockTestEndpoint }),
}));

jest.mock('../AutoConfigureDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

import EndpointCreateDrawer from '../EndpointCreateDrawer';

type User = ReturnType<typeof userEvent.setup>;

const nextButton = () => screen.getByRole('button', { name: /^next$/i });
const createButton = () =>
  screen.getByRole('button', { name: /^create endpoint$/i });

function renderDrawer(onCreated = jest.fn()) {
  render(
    <EndpointCreateDrawer
      open
      onClose={jest.fn()}
      onCreated={onCreated}
      projectId="proj-1"
    />
  );
  return onCreated;
}

async function fillToMapping(user: User) {
  expect(nextButton()).toBeDisabled();
  await user.type(screen.getByLabelText(/endpoint name/i), 'My Endpoint');
  await user.click(nextButton());
  fireEvent.change(screen.getByLabelText(/endpoint url/i), {
    target: { value: 'https://api.example.com/chat' },
  });
  await user.click(nextButton());
  fireEvent.change(screen.getByLabelText('API field for input'), {
    target: { value: 'q' },
  });
}

// Mapping the input sends the test by itself after a short pause.
const AUTO_RUN = { timeout: 3000 };

async function passMappingTest(user: User) {
  await screen.findByText('Test request successful', {}, AUTO_RUN);
  fireEvent.mouseDown(screen.getByLabelText('Response value for output'));
  await user.click(screen.getByRole('option', { name: '$.text' }));
}

describe('Endpoint create drawer — mapping test errors', () => {
  jest.setTimeout(15000);

  beforeEach(() => mockTestEndpoint.mockReset());

  it('shows why the target could not be reached', async () => {
    mockTestEndpoint.mockResolvedValue({
      error: true,
      error_type: 'network_error',
      output:
        'Could not reach api.example.com: it did not respond before the timeout.',
      message:
        'Could not reach api.example.com: it did not respond before the timeout.',
    });
    const user = userEvent.setup({ delay: null });
    renderDrawer();
    await fillToMapping(user);

    expect(
      await screen.findByText(
        'Could not reach api.example.com: it did not respond before the timeout.',
        {},
        AUTO_RUN
      )
    ).toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it('shows a rejected request without masking it', async () => {
    mockTestEndpoint.mockRejectedValue(
      new Error(
        'API error: 502 - This endpoint uses OAuth 2.0 client credentials, and the token request to auth.example.com failed: HTTP 500'
      )
    );
    const user = userEvent.setup({ delay: null });
    renderDrawer();
    await fillToMapping(user);

    expect(
      await screen.findByText(
        /token request to auth\.example\.com failed/,
        {},
        AUTO_RUN
      )
    ).toBeInTheDocument();
  });
});

describe('Endpoint create drawer — steps and submit', () => {
  jest.setTimeout(20000);

  beforeEach(() => {
    mockTestEndpoint.mockReset();
    mockTestEndpoint.mockResolvedValue({ raw_response: { text: 'hi' } });
    mockCreateEndpoint.mockReset();
    mockNotificationsShow.mockClear();
  });

  it('moves to the next step on Enter once the step is complete', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();

    await user.type(screen.getByLabelText(/endpoint name/i), '{Enter}');
    expect(screen.queryByLabelText(/endpoint url/i)).not.toBeInTheDocument();

    await user.type(
      screen.getByLabelText(/endpoint name/i),
      'My Endpoint{Enter}'
    );
    expect(screen.getByLabelText(/endpoint url/i)).toBeInTheDocument();
  });

  it('needs a passing mapping test and an output mapping before Next', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();
    await fillToMapping(user);
    expect(nextButton()).toBeDisabled();

    await passMappingTest(user);
    expect(nextButton()).toBeEnabled();
  });

  it('asks for a new test after the URL changes', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();
    await fillToMapping(user);
    await passMappingTest(user);

    await user.click(screen.getByRole('button', { name: /connection/i }));
    fireEvent.change(screen.getByLabelText(/endpoint url/i), {
      target: { value: 'https://api.example.com/v2/chat' },
    });
    await user.click(nextButton());
    expect(nextButton()).toBeDisabled();
  });

  async function runToCreate(user: User) {
    await fillToMapping(user);
    await passMappingTest(user);
    await user.click(nextButton());

    expect(createButton()).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Value for input' }), {
      target: { value: 'Hello' },
    });
    await user.click(
      screen.getByRole('button', { name: /send test request/i })
    );
    await screen.findByText('Endpoint is ready');
    await user.click(createButton());
  }

  it('creates the endpoint once the Test step passes', async () => {
    mockCreateEndpoint.mockResolvedValue({
      success: true,
      data: { id: 'ep-1' },
    });
    const user = userEvent.setup({ delay: null });
    const onCreated = renderDrawer();
    await runToCreate(user);

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(mockCreateEndpoint).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'My Endpoint',
        url: 'https://api.example.com/chat',
        project_id: 'proj-1',
        request_mapping: { q: '{{ input }}' },
        response_mapping: { output: '$.text' },
      })
    );
    expect(mockNotificationsShow).toHaveBeenCalledWith(
      'Endpoint created successfully!',
      expect.objectContaining({ severity: 'success' })
    );
  });

  it('shows the backend error when the org is over its endpoints quota', async () => {
    // createEndpoint never throws on a business failure -- it returns
    // {success: false, error}.
    mockCreateEndpoint.mockResolvedValue({
      success: false,
      error:
        'API error: 402 - Your organization is at its endpoints limit (1 of 1).',
    });
    const user = userEvent.setup({ delay: null });
    const onCreated = renderDrawer();
    await runToCreate(user);

    expect(
      await screen.findByText(
        'Your organization is at its endpoints limit (1 of 1).'
      )
    ).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(mockNotificationsShow).not.toHaveBeenCalledWith(
      'Endpoint created successfully!',
      expect.anything()
    );
  });
});
