import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';

import { OnboardingProvider, useOnboarding } from '../OnboardingContext';
import type { OnboardingProgress } from '@/types/onboarding';
import type { OnboardingStatus } from '@/utils/api-client/interfaces/user';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1', organization_id: 'org-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('../ActiveProjectContext', () => ({
  useActiveProject: () => ({ projects: [{ id: 'project-1' }], loading: false }),
}));

jest.mock('driver.js', () => ({
  driver: () => ({
    destroy: jest.fn(),
    getState: () => ({ isInitialized: false }),
    getConfig: jest.fn(),
    setSteps: jest.fn(),
    drive: jest.fn(),
    moveNext: jest.fn(),
    movePrevious: jest.fn(),
  }),
}));
jest.mock('driver.js/dist/driver.css', () => ({}));

let mockServerStatus: OnboardingStatus | undefined;
const mockUseOnboardingStatus = jest.fn((_enabled: boolean) => ({
  data: mockServerStatus,
}));

jest.mock('@/hooks/useOnboardingStatus', () => ({
  useOnboardingStatus: (enabled: boolean) => mockUseOnboardingStatus(enabled),
}));

let mockStoredProgress: Partial<OnboardingProgress> = {};

jest.mock('@/utils/onboarding-service', () => {
  const actual = jest.requireActual('@/utils/onboarding-service');
  return {
    ...actual,
    loadProgress: () => ({
      ...actual.getDefaultProgress(),
      ...mockStoredProgress,
    }),
    saveProgress: jest.fn(),
    loadProgressFromDatabase: jest.fn(() =>
      Promise.resolve(actual.getDefaultProgress())
    ),
    syncProgressToDatabase: jest.fn(() => Promise.resolve(true)),
  };
});

const NOTHING_DONE: OnboardingStatus = {
  project_created: false,
  endpoint_setup: false,
  users_invited: false,
  test_cases_created: false,
};

function Probe() {
  const { progress, completionPercentage, isComplete } = useOnboarding();
  return (
    <div>
      <span data-testid="percentage">{completionPercentage}</span>
      <span data-testid="endpoint">{String(progress.endpointSetup)}</span>
      <span data-testid="project">{String(progress.projectCreated)}</span>
      <span data-testid="complete">{String(isComplete)}</span>
    </div>
  );
}

function renderProvider() {
  return render(
    <OnboardingProvider>
      <Probe />
    </OnboardingProvider>
  );
}

describe('OnboardingProvider with server status', () => {
  beforeEach(() => {
    mockServerStatus = undefined;
    mockStoredProgress = {};
    mockUseOnboardingStatus.mockClear();
  });

  it('counts steps the backend found in real data', async () => {
    mockServerStatus = {
      ...NOTHING_DONE,
      endpoint_setup: true,
      test_cases_created: true,
    };

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId('percentage')).toHaveTextContent('67')
    );
    expect(screen.getByTestId('endpoint')).toHaveTextContent('true');
  });

  it('keeps local progress when the backend reports nothing done', async () => {
    mockStoredProgress = { projectCreated: true };
    mockServerStatus = NOTHING_DONE;

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId('project')).toHaveTextContent('true')
    );
    expect(screen.getByTestId('percentage')).toHaveTextContent('33');
  });

  it('does not count the optional invite step', async () => {
    mockServerStatus = { ...NOTHING_DONE, users_invited: true };

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId('percentage')).toHaveTextContent('0')
    );
  });

  it('reports completion when the backend covers every required step', async () => {
    mockServerStatus = {
      project_created: true,
      endpoint_setup: true,
      users_invited: false,
      test_cases_created: true,
    };

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId('complete')).toHaveTextContent('true')
    );
  });

  it('stops asking the backend once the checklist is dismissed', () => {
    mockStoredProgress = { dismissed: true };

    renderProvider();

    expect(mockUseOnboardingStatus).toHaveBeenLastCalledWith(
      expect.objectContaining({ dismissed: true })
    );
  });
});
