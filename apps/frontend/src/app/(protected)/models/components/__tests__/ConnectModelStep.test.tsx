import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import ConnectModelStep, { CONNECT_MODEL_COPY } from '../ConnectModelStep';

const mockRefreshFeatures = jest.fn();
const mockCreateModel = jest.fn();
const mockHandleSignOut = jest.fn();
const mockSetChecklistHidden = jest.fn();
let mockRhesisKeyEnabled = true;
let mockCanAddModel = true;

jest.mock('@/contexts/FeaturesContext', () => ({
  useRhesisKeyEnabled: () => mockRhesisKeyEnabled,
  useRefreshFeatures: () => mockRefreshFeatures,
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => mockCanAddModel,
  useCanWithStatus: () => ({ allowed: mockCanAddModel, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => mockCanAddModel,
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ setChecklistHidden: mockSetChecklistHidden }),
}));

jest.mock('@/actions/auth', () => ({
  handleSignOut: () => mockHandleSignOut(),
}));

jest.mock('@/hooks/useLookups', () => ({
  useTypeLookups: () => ({ data: [{ id: 'p1', type_value: 'openai' }] }),
}));

jest.mock('@/hooks/useCreateModel', () => ({
  useCreateModel: () => mockCreateModel,
}));

// The real drawers are covered by their own page; here they only need to show
// that the step opens them and wires their callbacks.
jest.mock('../PlatformKeyDrawer', () => ({
  PlatformKeyDrawer: ({ open }: { open: boolean }) =>
    open ? <div data-testid="platform-key-drawer" /> : null,
}));

jest.mock('../ModelConnectionDrawer', () => ({
  ModelConnectionDrawer: ({
    open,
    onClose,
    onConnect,
    providers,
  }: {
    open: boolean;
    onClose: () => void;
    onConnect: (providerId: string, data: unknown) => Promise<unknown>;
    providers: unknown[];
  }) =>
    open ? (
      <div data-testid="model-connection-drawer">
        <span data-testid="provider-count">{providers.length}</span>
        <button
          onClick={async () => {
            await onConnect('openai', { name: 'My model' });
            onClose();
          }}
        >
          finish connect
        </button>
      </div>
    ) : null,
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockRhesisKeyEnabled = true;
  mockCanAddModel = true;
  mockRefreshFeatures.mockResolvedValue(undefined);
  mockCreateModel.mockResolvedValue({ id: 'model-1' });
});

describe('ConnectModelStep', () => {
  it('offers both ways to connect a model', () => {
    render(<ConnectModelStep />);

    expect(
      screen.getByRole('heading', { name: CONNECT_MODEL_COPY.title })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.platformKeyAction })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.ownModelAction })
    ).toBeInTheDocument();
  });

  it('hides the platform key option when the deployment has none', () => {
    mockRhesisKeyEnabled = false;

    render(<ConnectModelStep />);

    expect(
      screen.queryByRole('button', {
        name: CONNECT_MODEL_COPY.platformKeyAction,
      })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.ownModelAction })
    ).toBeInTheDocument();
  });

  it('points a user who can do neither at an admin', () => {
    mockRhesisKeyEnabled = false;
    mockCanAddModel = false;

    render(<ConnectModelStep />);

    expect(screen.getByText(CONNECT_MODEL_COPY.noAccess)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: CONNECT_MODEL_COPY.ownModelAction })
    ).not.toBeInTheDocument();
  });

  it('opens the existing platform key drawer', async () => {
    render(<ConnectModelStep />);

    await userEvent.click(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.platformKeyAction })
    );

    expect(
      await screen.findByTestId('platform-key-drawer')
    ).toBeInTheDocument();
  });

  it('creates the model through the existing drawer, then refetches features', async () => {
    render(<ConnectModelStep />);

    await userEvent.click(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.ownModelAction })
    );
    expect(await screen.findByTestId('provider-count')).toHaveTextContent('1');
    expect(mockRefreshFeatures).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole('button', { name: 'finish connect' })
    );

    await waitFor(() => expect(mockRefreshFeatures).toHaveBeenCalledTimes(1));
    expect(mockCreateModel).toHaveBeenCalledWith({ name: 'My model' });
  });

  it('keeps sign-out reachable', async () => {
    render(<ConnectModelStep />);

    await userEvent.click(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.signOut })
    );

    expect(mockHandleSignOut).toHaveBeenCalledTimes(1);
  });

  it('hides the onboarding checklist while it is up', () => {
    const { unmount } = render(<ConnectModelStep />);
    expect(mockSetChecklistHidden).toHaveBeenLastCalledWith(true);

    unmount();
    expect(mockSetChecklistHidden).toHaveBeenLastCalledWith(false);
  });

  it('refetches features on "Check again"', async () => {
    render(<ConnectModelStep />);

    await userEvent.click(
      screen.getByRole('button', { name: CONNECT_MODEL_COPY.checkAgain })
    );

    await waitFor(() => expect(mockRefreshFeatures).toHaveBeenCalledTimes(1));
  });
});
