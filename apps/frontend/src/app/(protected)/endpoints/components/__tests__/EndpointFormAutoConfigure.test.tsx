import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
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

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
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

jest.mock('@/actions/endpoints', () => ({
  createEndpoint: jest.fn(),
}));

jest.mock('@/actions/endpoints/auto-configure', () => ({
  autoConfigureEndpoint: jest.fn(),
}));

jest.mock('../AutoConfigureDrawer', () => {
  const MockDrawer = ({
    open,
    onClose,
    onApply,
  }: {
    open: boolean;
    onClose: () => void;
    onApply: (result: Record<string, unknown>) => void;
  }) =>
    open ? (
      <div data-testid="auto-configure-drawer">
        <button onClick={onClose}>Close Drawer</button>
        <button
          onClick={() =>
            onApply({
              request_mapping: { query: '{{ input }}' },
              response_mapping: { output: '$.response' },
              request_headers: { 'Content-Type': 'application/json' },
              url: 'https://api.example.com',
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

import EndpointForm from '../EndpointForm';

// Navigate to the Mapping tab (index 2).
async function navigateToBodyStep(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.queryByText('Loading projects...')).not.toBeInTheDocument()
  );

  await user.click(screen.getByRole('tab', { name: /mapping/i }));
}

describe('EndpointForm — Body step auto-configure', () => {
  jest.setTimeout(10000);

  it('renders the auto-configure button on the body step', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);
    await navigateToBodyStep(user);

    expect(
      screen.getByRole('button', { name: /auto mapping/i })
    ).toBeInTheDocument();
  });

  it('clicking auto-configure opens the drawer', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);
    await navigateToBodyStep(user);

    await user.click(screen.getByRole('button', { name: /auto mapping/i }));

    expect(screen.getByTestId('auto-configure-drawer')).toBeInTheDocument();
  });

  it('auth token field is in the connection tab', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);

    await waitFor(() =>
      expect(screen.queryByText('Loading projects...')).not.toBeInTheDocument()
    );

    // On the Overview tab there is no auth token field
    expect(screen.queryByLabelText(/api token/i)).not.toBeInTheDocument();

    // Click the Connection tab (headers merged into Connection)
    await user.click(screen.getByRole('tab', { name: /connection/i }));

    // Auth token should now be visible in the Connection tab
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });
});
