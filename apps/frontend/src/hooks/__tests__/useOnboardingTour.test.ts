import { renderHook } from '@testing-library/react';
import { useOnboardingTour } from '../useOnboardingTour';

const mockStartTour = jest.fn();

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ startTour: mockStartTour }),
}));

// next/navigation useSearchParams is mocked globally in jest.setup.js
// We override it per-test below
const mockUseSearchParams = jest.fn();

jest.mock('next/navigation', () => ({
  ...jest.requireActual('next/navigation'),
  useSearchParams: () => mockUseSearchParams(),
  usePathname: () => '/',
  useRouter: () => ({ push: jest.fn() }),
}));

describe('useOnboardingTour', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    // Default: no ?tour= param
    mockUseSearchParams.mockReturnValue({ get: () => null });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('does not start any tour when there is no tour param in the URL', () => {
    renderHook(() => useOnboardingTour('dashboard-tour'));

    jest.runAllTimers();

    expect(mockStartTour).not.toHaveBeenCalled();
  });

  it('does not start a tour when tourId is not provided', () => {
    mockUseSearchParams.mockReturnValue({ get: () => 'dashboard-tour' });

    renderHook(() => useOnboardingTour(undefined));

    jest.runAllTimers();

    expect(mockStartTour).not.toHaveBeenCalled();
  });

  it('does not start a tour when the URL param does not match the tourId', () => {
    mockUseSearchParams.mockReturnValue({ get: () => 'other-tour' });

    renderHook(() => useOnboardingTour('dashboard-tour'));

    jest.runAllTimers();

    expect(mockStartTour).not.toHaveBeenCalled();
  });

  it('starts the tour after a delay when tour param matches the tourId', () => {
    mockUseSearchParams.mockReturnValue({ get: () => 'dashboard-tour' });

    renderHook(() => useOnboardingTour('dashboard-tour'));

    // Should not have fired yet (500ms delay)
    expect(mockStartTour).not.toHaveBeenCalled();

    jest.advanceTimersByTime(500);

    expect(mockStartTour).toHaveBeenCalledTimes(1);
    expect(mockStartTour).toHaveBeenCalledWith('dashboard-tour');
  });

  it('cancels the timer on unmount before it fires', () => {
    mockUseSearchParams.mockReturnValue({ get: () => 'dashboard-tour' });

    const { unmount } = renderHook(() => useOnboardingTour('dashboard-tour'));

    // Unmount before the 500ms delay fires
    unmount();

    jest.advanceTimersByTime(600);

    expect(mockStartTour).not.toHaveBeenCalled();
  });
});
