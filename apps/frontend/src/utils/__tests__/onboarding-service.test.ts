import {
  getDefaultProgress,
  calculateCompletionPercentage,
  isOnboardingComplete,
  mergeProgress,
  loadProgress,
  saveProgress,
  clearProgress,
} from '../onboarding-service';
import type { OnboardingProgress } from '@/types/onboarding';

describe('getDefaultProgress', () => {
  it('returns all steps as false', () => {
    const progress = getDefaultProgress();
    expect(progress.projectCreated).toBe(false);
    expect(progress.endpointSetup).toBe(false);
    expect(progress.usersInvited).toBe(false);
    expect(progress.testCasesCreated).toBe(false);
    expect(progress.dismissed).toBe(false);
  });

  it('includes a lastUpdated timestamp', () => {
    const progress = getDefaultProgress();
    expect(typeof progress.lastUpdated).toBe('number');
    expect(progress.lastUpdated).toBeGreaterThan(0);
  });
});

describe('calculateCompletionPercentage', () => {
  it('returns 0 for no steps completed', () => {
    expect(calculateCompletionPercentage(getDefaultProgress())).toBe(0);
  });

  it('returns 25 for one step completed', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
    };
    expect(calculateCompletionPercentage(progress)).toBe(25);
  });

  it('returns 50 for two steps completed', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
      endpointSetup: true,
    };
    expect(calculateCompletionPercentage(progress)).toBe(50);
  });

  it('returns 100 for all four steps completed', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
      endpointSetup: true,
      usersInvited: true,
      testCasesCreated: true,
    };
    expect(calculateCompletionPercentage(progress)).toBe(100);
  });

  it('does not count dismissed in completion', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      dismissed: true,
    };
    expect(calculateCompletionPercentage(progress)).toBe(0);
  });
});

describe('isOnboardingComplete', () => {
  it('returns false when no steps are completed', () => {
    expect(isOnboardingComplete(getDefaultProgress())).toBe(false);
  });

  it('returns false when only some required steps are done', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
      endpointSetup: true,
    };
    expect(isOnboardingComplete(progress)).toBe(false);
  });

  it('returns true when required steps are done (usersInvited is optional)', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
      endpointSetup: true,
      testCasesCreated: true,
    };
    expect(isOnboardingComplete(progress)).toBe(true);
  });

  it('returns true when all steps are done', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
      endpointSetup: true,
      usersInvited: true,
      testCasesCreated: true,
    };
    expect(isOnboardingComplete(progress)).toBe(true);
  });
});

describe('mergeProgress', () => {
  it('merges with OR logic (completed steps stay completed)', () => {
    const local: OnboardingProgress = {
      projectCreated: true,
      endpointSetup: false,
      usersInvited: false,
      testCasesCreated: false,
      dismissed: false,
      lastUpdated: 1000,
    };

    const remote: OnboardingProgress = {
      projectCreated: false,
      endpointSetup: true,
      usersInvited: false,
      testCasesCreated: false,
      dismissed: false,
      lastUpdated: 2000,
    };

    const merged = mergeProgress(local, remote);
    expect(merged.projectCreated).toBe(true);
    expect(merged.endpointSetup).toBe(true);
    expect(merged.usersInvited).toBe(false);
  });

  it('takes the latest lastUpdated timestamp', () => {
    const local: OnboardingProgress = {
      ...getDefaultProgress(),
      lastUpdated: 1000,
    };
    const remote: OnboardingProgress = {
      ...getDefaultProgress(),
      lastUpdated: 5000,
    };

    expect(mergeProgress(local, remote).lastUpdated).toBe(5000);
    expect(mergeProgress(remote, local).lastUpdated).toBe(5000);
  });

  it('merges dismissed flag with OR', () => {
    const local: OnboardingProgress = {
      ...getDefaultProgress(),
      dismissed: true,
      lastUpdated: 1000,
    };
    const remote: OnboardingProgress = {
      ...getDefaultProgress(),
      dismissed: false,
      lastUpdated: 2000,
    };

    expect(mergeProgress(local, remote).dismissed).toBe(true);
  });
});

describe('loadProgress', () => {
  let getItemSpy: jest.SpyInstance;

  beforeEach(() => {
    getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
  });

  afterEach(() => {
    getItemSpy.mockRestore();
  });

  it('returns default progress when localStorage is empty', () => {
    getItemSpy.mockReturnValue(null);
    const progress = loadProgress();
    expect(progress.projectCreated).toBe(false);
  });

  it('parses stored progress from localStorage', () => {
    const stored = JSON.stringify({
      projectCreated: true,
      endpointSetup: true,
    });
    getItemSpy.mockReturnValue(stored);
    const progress = loadProgress();
    expect(progress.projectCreated).toBe(true);
    expect(progress.endpointSetup).toBe(true);
    // Unset fields should be filled from defaults
    expect(progress.usersInvited).toBe(false);
  });

  it('returns default progress on parse error', () => {
    getItemSpy.mockReturnValue('invalid-json');
    const progress = loadProgress();
    expect(progress.projectCreated).toBe(false);
  });
});

describe('saveProgress', () => {
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    setItemSpy = jest.spyOn(Storage.prototype, 'setItem');
  });

  afterEach(() => {
    setItemSpy.mockRestore();
  });

  it('saves progress to localStorage', () => {
    const progress: OnboardingProgress = {
      ...getDefaultProgress(),
      projectCreated: true,
    };
    saveProgress(progress);
    expect(setItemSpy).toHaveBeenCalledWith(
      'rhesis_onboarding_progress',
      expect.any(String)
    );
  });

  it('includes lastUpdated in saved data', () => {
    saveProgress(getDefaultProgress());
    const savedValue = setItemSpy.mock.calls[0][1];
    const parsed = JSON.parse(savedValue);
    expect(typeof parsed.lastUpdated).toBe('number');
  });
});

describe('clearProgress', () => {
  let removeItemSpy: jest.SpyInstance;

  beforeEach(() => {
    removeItemSpy = jest.spyOn(Storage.prototype, 'removeItem');
  });

  afterEach(() => {
    removeItemSpy.mockRestore();
  });

  it('removes progress from localStorage', () => {
    clearProgress();
    expect(removeItemSpy).toHaveBeenCalledWith('rhesis_onboarding_progress');
  });
});
