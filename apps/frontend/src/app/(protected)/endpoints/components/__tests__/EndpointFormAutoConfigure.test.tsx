import React from 'react';
import { render, screen } from '@testing-library/react';
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

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ markStepComplete: jest.fn() }),
}));

jest.mock('@/hooks/useQuotaGate', () => ({
  useQuotaGate: () => ({ exhausted: false, notice: null }),
}));

jest.mock('@/hooks/useCreateEndpoint', () => ({
  useCreateEndpoint: () => jest.fn(),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useTestEndpoint: () => ({ mutateAsync: jest.fn() }),
}));

jest.mock('../AutoConfigureDrawer', () => {
  const MockDrawer = ({
    open,
    onApply,
  }: {
    open: boolean;
    onApply: (result: Record<string, unknown>) => void;
  }) =>
    open ? (
      <div data-testid="auto-configure-drawer">
        <button
          onClick={() =>
            onApply({
              request_mapping: { query: '{{ input }}' },
              response_mapping: { output: '$.response' },
              url: 'https://api.example.com/chat',
              method: 'POST',
              status: 'success',
            })
          }
        >
          Apply Result
        </button>
      </div>
    ) : null;
  return { __esModule: true, default: MockDrawer };
});

import EndpointCreateDrawer from '../EndpointCreateDrawer';

function renderDrawer() {
  render(
    <EndpointCreateDrawer
      open
      onClose={jest.fn()}
      onCreated={jest.fn()}
      projectId="proj-1"
    />
  );
}

describe('Endpoint create drawer — auto-configure', () => {
  jest.setTimeout(10000);

  it('opens auto-configure from the Overview step', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();

    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    expect(screen.getByTestId('auto-configure-drawer')).toBeInTheDocument();
  });

  it('fills the URL and request mapping from the result, even without headers', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();

    await user.click(screen.getByRole('button', { name: /auto-configure/i }));
    await user.click(screen.getByRole('button', { name: /apply result/i }));
    await user.type(screen.getByLabelText(/endpoint name/i), 'My Endpoint');
    await user.click(screen.getByRole('button', { name: /^next$/i }));

    expect(screen.getByLabelText(/endpoint url/i)).toHaveValue(
      'https://api.example.com/chat'
    );

    await user.click(screen.getByRole('button', { name: /^next$/i }));
    expect(screen.getByLabelText('API field for input')).toHaveValue('query');
  });

  it('puts the auth token field on the Connection step', async () => {
    const user = userEvent.setup({ delay: null });
    renderDrawer();

    expect(screen.queryByLabelText(/api token/i)).not.toBeInTheDocument();

    await user.type(screen.getByLabelText(/endpoint name/i), 'My Endpoint');
    await user.click(screen.getByRole('button', { name: /^next$/i }));

    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });
});
