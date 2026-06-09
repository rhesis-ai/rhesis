import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

jest.mock('../AutoConfigureModal', () => {
  const MockModal = ({
    open,
    onClose,
    onApply,
  }: {
    open: boolean;
    onClose: () => void;
    onApply: (result: Record<string, unknown>) => void;
  }) =>
    open ? (
      <div data-testid="auto-configure-modal">
        <button onClick={onClose}>Close Modal</button>
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
  return { __esModule: true, default: MockModal };
});

import EndpointForm from '../EndpointForm';

// Navigate from step 0 to step 2 (body/mapping step).
// Relies on useParams returning identifier:'proj-1' so project_id is pre-filled.
async function navigateToBodyStep(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.queryByText('Loading projects...')).not.toBeInTheDocument()
  );

  // Fill required fields in step 0
  fireEvent.change(screen.getByRole('textbox', { name: /endpoint name/i }), {
    target: { value: 'My API' },
  });
  fireEvent.change(screen.getByRole('textbox', { name: /endpoint url/i }), {
    target: { value: 'https://api.example.com' },
  });

  // project_id is pre-filled via useParams identifier; click Next twice
  await user.click(screen.getByRole('button', { name: /next →/i }));
  await user.click(screen.getByRole('button', { name: /next →/i }));
}

describe('EndpointForm — Body step auto-configure', () => {
  jest.setTimeout(10000);

  it('renders the auto-configure button on the body step', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);
    await navigateToBodyStep(user);

    expect(
      screen.getByRole('button', { name: /auto-configure/i })
    ).toBeInTheDocument();
  });

  it('clicking auto-configure opens the modal', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);
    await navigateToBodyStep(user);

    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    expect(screen.getByTestId('auto-configure-modal')).toBeInTheDocument();
  });

  it('auth token field is in the headers step (step 1)', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);

    // On step 0 (basics) there is no auth token field
    expect(screen.queryByLabelText(/api token/i)).not.toBeInTheDocument();

    await waitFor(() =>
      expect(screen.queryByText('Loading projects...')).not.toBeInTheDocument()
    );

    // Fill basics and advance to step 1
    fireEvent.change(screen.getByRole('textbox', { name: /endpoint name/i }), {
      target: { value: 'My API' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /endpoint url/i }), {
      target: { value: 'https://api.example.com' },
    });
    await user.click(screen.getByRole('button', { name: /next →/i }));

    // Auth token should now be visible in step 1 (headers)
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });
});
