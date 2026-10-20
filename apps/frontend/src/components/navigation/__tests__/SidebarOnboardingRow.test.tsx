import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { renderToString } from 'react-dom/server';
import { SidebarOnboardingRow } from '../SidebarOnboardingRow';
import type { OnboardingProgress } from '@/types/onboarding';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'authenticated' }),
}));

const mockDismiss = jest.fn();
let mockProgress: OnboardingProgress;
let mockChecklistHidden = false;
let mockIsComplete = false;

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({
    progress: mockProgress,
    isComplete: mockIsComplete,
    completionPercentage: 50,
    dismissOnboarding: mockDismiss,
    checklistHidden: mockChecklistHidden,
  }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockChecklistHidden = false;
  mockIsComplete = false;
  mockProgress = {
    endpointSetup: true,
    agentTested: true,
    insightsReviewed: false,
    usersInvited: false,
    dismissed: false,
    lastUpdated: 0,
  };
});

const row = () =>
  screen.queryByRole('button', { name: /getting started, 2 of 3 done/i });

describe('SidebarOnboardingRow', () => {
  it('renders nothing on the server so hydration matches', () => {
    expect(renderToString(<SidebarOnboardingRow />)).toBe('');
  });

  it('shows the label and done count', () => {
    render(<SidebarOnboardingRow />);
    expect(row()).toBeInTheDocument();
    expect(screen.getByText('Getting started')).toBeInTheDocument();
    expect(screen.getByText('2 of 3 done')).toBeInTheDocument();
  });

  it('does not count the optional invite step', () => {
    mockProgress.usersInvited = true;
    render(<SidebarOnboardingRow />);
    expect(screen.getByText('2 of 3 done')).toBeInTheDocument();
  });

  it.each([
    ['a full-screen step hides it', () => (mockChecklistHidden = true)],
    ['it was dismissed', () => (mockProgress.dismissed = true)],
    ['every step is done', () => (mockIsComplete = true)],
  ])('renders nothing when %s', (_case, arrange) => {
    arrange();
    render(<SidebarOnboardingRow />);
    expect(row()).not.toBeInTheDocument();
  });

  it('shows only the ring and remaining count when collapsed', () => {
    render(<SidebarOnboardingRow collapsed />);
    expect(row()).toBeInTheDocument();
    expect(screen.queryByText('Getting started')).not.toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('opens the checklist and closes it when a step is picked', async () => {
    render(<SidebarOnboardingRow />);
    fireEvent.click(row() as HTMLElement);
    const steps = () =>
      screen.queryByRole('list', { name: 'Onboarding steps' });
    expect(steps()).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Review insights' }));
    expect(mockPush).toHaveBeenCalledWith('/insights');
    await waitFor(() => expect(steps()).not.toBeInTheDocument());
  });

  it('dismisses only after confirming', () => {
    render(<SidebarOnboardingRow />);
    fireEvent.click(row() as HTMLElement);
    fireEvent.click(screen.getByRole('button', { name: 'Hide this guide' }));
    expect(mockDismiss).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Hide' }));
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });
});
