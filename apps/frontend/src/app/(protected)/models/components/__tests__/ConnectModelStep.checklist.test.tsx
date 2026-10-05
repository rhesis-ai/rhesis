import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import ConnectModelStep from '../ConnectModelStep';
import OnboardingChecklist from '@/components/onboarding/OnboardingChecklist';
import { useOnboarding } from '@/contexts/OnboardingContext';

// The real checklist next to the real step, sharing one `checklistHidden`
// flag the way the root layout's OnboardingProvider does.
jest.mock('@/contexts/OnboardingContext', () => {
  const ReactActual = jest.requireActual<typeof import('react')>('react');
  const Context = ReactActual.createContext<unknown>(undefined);
  return {
    OnboardingProvider: ({ children }: { children: React.ReactNode }) => {
      const [checklistHidden, setChecklistHidden] = ReactActual.useState(false);
      return (
        <Context.Provider
          value={{
            progress: {
              projectCreated: false,
              endpointSetup: false,
              usersInvited: false,
              testCasesCreated: false,
              dismissed: false,
              lastUpdated: 0,
            },
            isComplete: false,
            completionPercentage: 0,
            dismissOnboarding: jest.fn(),
            checklistHidden,
            setChecklistHidden,
          }}
        >
          {children}
        </Context.Provider>
      );
    },
    useOnboarding: () => ReactActual.useContext(Context),
  };
});

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/tests',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/contexts/FeaturesContext', () => ({
  useRhesisKeyEnabled: () => true,
  useRefreshFeatures: () => jest.fn(),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/actions/auth', () => ({ handleSignOut: jest.fn() }));
jest.mock('@/hooks/useLookups', () => ({
  useTypeLookups: () => ({ data: [] }),
}));
jest.mock('@/hooks/useCreateModel', () => ({
  useCreateModel: () => jest.fn(),
}));
jest.mock('../PlatformKeyDrawer', () => ({ PlatformKeyDrawer: () => null }));
jest.mock('../ModelConnectionDrawer', () => ({
  ModelConnectionDrawer: () => null,
}));

const { OnboardingProvider } = jest.requireMock(
  '@/contexts/OnboardingContext'
) as {
  OnboardingProvider: React.ComponentType<{ children: React.ReactNode }>;
  useOnboarding: typeof useOnboarding;
};

function Harness({ gated }: { gated: boolean }) {
  return (
    <OnboardingProvider>
      {gated ? <ConnectModelStep /> : <div>app</div>}
      <OnboardingChecklist />
    </OnboardingProvider>
  );
}

const checklist = () =>
  screen.queryByRole('complementary', { name: 'Onboarding checklist' }) ??
  screen.queryByLabelText('Onboarding checklist');

describe('ConnectModelStep and the onboarding checklist', () => {
  it('hides the checklist while the step is mounted and restores it after', () => {
    const { rerender } = render(<Harness gated />);
    expect(checklist()).not.toBeInTheDocument();

    rerender(<Harness gated={false} />);
    expect(checklist()).toBeInTheDocument();

    rerender(<Harness gated />);
    expect(checklist()).not.toBeInTheDocument();
  });
});
