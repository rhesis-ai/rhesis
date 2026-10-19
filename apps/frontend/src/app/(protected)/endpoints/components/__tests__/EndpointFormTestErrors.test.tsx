import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

jest.mock(
  'next/dynamic',
  () => (loader: () => Promise<{ default: React.ComponentType }>) => {
    function DynamicComponent(props: Record<string, unknown>) {
      const [Comp, setComp] = React.useState<React.ComponentType | null>(null);
      React.useEffect(() => {
        loader().then(mod => {
          setComp(() => mod.default ?? (mod as unknown as React.ComponentType));
        });
      }, []);
      if (!Comp) return null;
      return React.createElement(Comp, props);
    }
    DynamicComponent.displayName = 'DynamicComponent';
    return DynamicComponent;
  }
);

const mockRouterPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush, replace: jest.fn() }),
  // Supply a project identifier so project_id is pre-filled and step 0 is valid
  useParams: () => ({ identifier: 'proj-1' }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'test-token' },
    status: 'authenticated',
  }),
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

const mockNotificationsShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockNotificationsShow }),
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ markStepComplete: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({
      getProjects: jest
        .fn()
        .mockResolvedValue([
          { id: 'proj-1', name: 'Test Project', description: 'A test project' },
        ]),
    }),
    getEndpointsClient: () => ({
      testEndpoint: jest.fn(),
    }),
  })),
}));

const mockCreateEndpoint = jest.fn();
jest.mock('@/actions/endpoints', () => ({
  createEndpoint: (...args: unknown[]) => mockCreateEndpoint(...args),
}));

jest.mock('@/actions/endpoints/auto-configure', () => ({
  autoConfigureEndpoint: jest.fn(),
}));

const mockTestEndpoint = jest.fn();
jest.mock('@/hooks/useEndpoints', () => ({
  useTestEndpoint: () => ({ mutateAsync: mockTestEndpoint }),
}));

import EndpointForm from '../EndpointForm';

async function runConnectionCheck(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.queryByText('Loading projects...')).not.toBeInTheDocument()
  );
  await user.click(screen.getByRole('tab', { name: /connection/i }));
  fireEvent.change(screen.getByLabelText(/endpoint url/i), {
    target: { value: 'https://api.example.com/chat' },
  });
  await user.click(screen.getByRole('tab', { name: /test/i }));
  await user.click(screen.getByRole('button', { name: /check connection/i }));
}

describe('EndpointForm — connection check errors', () => {
  jest.setTimeout(10000);

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
    render(<EndpointForm />);
    await runConnectionCheck(user);

    expect(
      await screen.findByText(
        'Could not reach api.example.com: it did not respond before the timeout.'
      )
    ).toBeInTheDocument();
  });

  it('shows a rejected request without masking it', async () => {
    mockTestEndpoint.mockRejectedValue(
      new Error(
        'API error: 502 - This endpoint uses OAuth 2.0 client credentials, and the token request to auth.example.com failed: HTTP 500'
      )
    );
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);
    await runConnectionCheck(user);

    expect(
      await screen.findByText(/token request to auth\.example\.com failed/)
    ).toBeInTheDocument();
  });
});
