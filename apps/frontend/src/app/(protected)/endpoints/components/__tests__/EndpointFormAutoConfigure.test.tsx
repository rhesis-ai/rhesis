import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
  useParams: () => ({
    identifier: undefined,
  }),
}));

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'test-token' },
    status: 'authenticated',
  }),
}));

// Mock Monaco Editor
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

// Mock NotificationContext
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({
    show: jest.fn(),
  }),
}));

// Mock OnboardingContext
jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({
    markStepComplete: jest.fn(),
  }),
}));

// Mock api-client
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

// Mock actions
jest.mock('@/actions/endpoints', () => ({
  createEndpoint: jest.fn(),
}));

jest.mock('@/actions/endpoints/auto-configure', () => ({
  autoConfigureEndpoint: jest.fn(),
}));

// Mock AutoConfigureModal to simplify form integration testing
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

// Import after all mocks
import EndpointForm from '../EndpointForm';

describe('EndpointForm Auto-configure Integration', () => {
  it('renders auto-configure button', async () => {
    render(<EndpointForm />);

    const button = screen.getByRole('button', { name: /auto-configure/i });
    expect(button).toBeInTheDocument();
  });

  it('auto-configure button is disabled when basic info is incomplete', () => {
    render(<EndpointForm />);

    const button = screen.getByRole('button', { name: /auto-configure/i });
    expect(button).toBeDisabled();
  });

  it('auto-configure button is enabled when basic info is complete', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);

    // Fill in name (use getByRole to avoid matching Tooltip aria-label)
    await user.type(screen.getByRole('textbox', { name: /name/i }), 'My API');

    // Fill in URL
    await user.type(
      screen.getByRole('textbox', { name: /url/i }),
      'https://api.example.com'
    );

    // Fill in auth token
    await user.type(screen.getByLabelText(/api token/i), 'test-token');

    const button = screen.getByRole('button', { name: /auto-configure/i });
    expect(button).not.toBeDisabled();
  });

  it('clicking auto-configure opens the modal', async () => {
    const user = userEvent.setup({ delay: null });
    render(<EndpointForm />);

    // Fill required fields (use getByRole to avoid matching Tooltip aria-label)
    await user.type(screen.getByRole('textbox', { name: /name/i }), 'My API');
    await user.type(
      screen.getByRole('textbox', { name: /url/i }),
      'https://api.example.com'
    );
    await user.type(screen.getByLabelText(/api token/i), 'test-token');

    // Click auto-configure
    await user.click(screen.getByRole('button', { name: /auto-configure/i }));

    expect(screen.getByTestId('auto-configure-modal')).toBeInTheDocument();
  });

  it('auth token field is in Basic Information tab', () => {
    render(<EndpointForm />);

    // We're on the Basic Information tab (tab 0) by default
    // Auth token should be visible
    expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
  });
});
