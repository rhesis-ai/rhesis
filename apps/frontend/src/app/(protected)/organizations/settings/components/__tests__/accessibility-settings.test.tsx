/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OrganizationAccessibilityForm from '../OrganizationAccessibilityForm';
import AccessibilityPreferenceForm from '../../../../settings/components/AccessibilityPreferenceForm';
import type { Organization } from '@/utils/api-client/interfaces/organization';

const updateOrganizationSettings = jest.fn().mockResolvedValue({});
const updateUserSettings = jest.fn().mockResolvedValue({});
let deploymentMode: boolean | undefined;
let orgContext: Organization | null = null;

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: jest.fn() }),
}));

jest.mock('@tanstack/react-query', () => ({
  ...jest.requireActual('@tanstack/react-query'),
  useQueryClient: () => ({}),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getOrganizationsClient: () => ({ updateOrganizationSettings }),
    getUsersClient: () => ({ updateUserSettings }),
  })),
}));

jest.mock('@/config/branding', () => ({
  getDeploymentBranding: () => ({ accessibilityMode: deploymentMode }),
}));

jest.mock('@/contexts/OrganizationContext', () => ({
  useOrganization: () => ({ organization: orgContext }),
}));

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useUserScope: () => 'user-1',
}));

jest.mock('@/hooks/useUserSettings', () => ({
  useUserSettings: () => ({ data: undefined }),
  writeUserSettingsCache: jest.fn(),
}));

function organization(mode?: boolean): Organization {
  return {
    id: 'org-1',
    name: 'Acme',
    createdAt: '2026-01-01',
    owner_id: 'u1' as any,
    user_id: 'u1' as any,
    organization_settings: {
      version: 1,
      branding: {},
      accessibility: { mode },
    },
  };
}

const modeSwitch = () =>
  screen.getByRole('checkbox', { name: 'Accessibility mode' });

beforeEach(() => {
  jest.clearAllMocks();
  deploymentMode = undefined;
  orgContext = null;
});

describe('OrganizationAccessibilityForm', () => {
  it('saves the mode in the accessibility section', async () => {
    const onUpdate = jest.fn();
    render(
      <OrganizationAccessibilityForm
        organization={organization()}
        onUpdate={onUpdate}
      />
    );

    fireEvent.click(modeSwitch());

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    expect(updateOrganizationSettings).toHaveBeenCalledWith({
      accessibility: { mode: true },
    });
  });

  it('is locked on when the deployment turns it on', () => {
    deploymentMode = true;
    render(
      <OrganizationAccessibilityForm
        organization={organization()}
        onUpdate={jest.fn()}
      />
    );

    expect(modeSwitch()).toBeChecked();
    expect(modeSwitch()).toBeDisabled();
    expect(
      screen.getByText(/Turned on for this whole deployment/)
    ).toBeInTheDocument();
  });
});

describe('AccessibilityPreferenceForm', () => {
  it('saves the mode in the personal UI settings', async () => {
    render(<AccessibilityPreferenceForm userSettings={undefined} />);

    fireEvent.click(modeSwitch());

    await waitFor(() =>
      expect(updateUserSettings).toHaveBeenCalledWith({
        ui: { accessibility_mode: true },
      })
    );
  });

  it('cannot be turned off where the organization turned it on', () => {
    orgContext = organization(true);
    render(<AccessibilityPreferenceForm userSettings={undefined} />);

    expect(modeSwitch()).toBeChecked();
    expect(modeSwitch()).toBeDisabled();
    expect(
      screen.getByText(/Turned on for your whole organization/)
    ).toBeInTheDocument();
  });
});
