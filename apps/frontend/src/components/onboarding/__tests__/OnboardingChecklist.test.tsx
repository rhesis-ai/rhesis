import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { createTheme } from '@mui/material/styles';
import OnboardingChecklist, {
  CHECKLIST_EXPANDED_STORAGE_KEY,
} from '../OnboardingChecklist';
import { ONBOARDING_COLLAPSE_PATH } from '@/config/onboarding-tours';

let mockPathname = '/projects';
let mockSearchParams = new URLSearchParams();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'authenticated' }),
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({
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
  }),
}));

let store: Record<string, string>;
const storage = {
  getItem: jest.fn((key: string) => (key in store ? store[key] : null)),
  setItem: jest.fn((key: string, value: string) => {
    store[key] = value;
  }),
  removeItem: jest.fn(),
  clear: jest.fn(),
};

beforeEach(() => {
  store = {};
  mockPathname = '/projects';
  mockSearchParams = new URLSearchParams();
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
  });
  jest.clearAllMocks();
});

const header = () =>
  screen.getByRole('button', { name: /(collapse|expand) checklist/i });

describe('OnboardingChecklist', () => {
  it('starts expanded when nothing is stored', () => {
    render(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'true');
  });

  it('restores a stored collapsed state', () => {
    store[CHECKLIST_EXPANDED_STORAGE_KEY] = 'false';
    render(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'false');
  });

  it('saves the state when the user toggles it', () => {
    render(<OnboardingChecklist />);
    fireEvent.click(header());
    expect(header()).toHaveAttribute('aria-expanded', 'false');
    expect(store[CHECKLIST_EXPANDED_STORAGE_KEY]).toBe('false');

    fireEvent.click(header());
    expect(store[CHECKLIST_EXPANDED_STORAGE_KEY]).toBe('true');
  });

  it('stays collapsed across route changes', () => {
    const { rerender } = render(<OnboardingChecklist />);
    fireEvent.click(header());

    mockPathname = '/test-sets';
    rerender(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'false');
  });

  it('collapses on the collapse path but does not re-expand after leaving it', () => {
    mockPathname = ONBOARDING_COLLAPSE_PATH;
    const { rerender } = render(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'false');

    mockPathname = '/projects';
    rerender(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'false');
  });

  it('collapses during a tour', () => {
    mockSearchParams = new URLSearchParams('tour=project');
    render(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'false');
  });

  it('renders and toggles when storage throws', () => {
    storage.getItem.mockImplementationOnce(() => {
      throw new Error('SecurityError');
    });
    storage.setItem.mockImplementationOnce(() => {
      throw new Error('QuotaExceededError');
    });
    render(<OnboardingChecklist />);
    expect(header()).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(header());
    expect(header()).toHaveAttribute('aria-expanded', 'false');
  });

  it('sits just below drawers', () => {
    render(<OnboardingChecklist />);
    const widget = screen.getByRole('complementary', {
      name: 'Onboarding checklist',
    });
    expect(widget).toHaveStyle({
      zIndex: String(createTheme().zIndex.drawer - 1),
    });
  });
});
