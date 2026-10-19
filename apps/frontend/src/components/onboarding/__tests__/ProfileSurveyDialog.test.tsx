import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProfileSurveyDialog from '../ProfileSurveyDialog';

const mockUpdateUserSettings = jest.fn();
const mockShow = jest.fn();
let mockSettings: { onboarding?: { profile_survey_pending?: boolean } } = {};

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/hooks/useUserSettings', () => ({
  useUserSettings: () => ({ data: mockSettings }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsersClient: () => ({
      updateUserSettings: mockUpdateUserSettings,
    }),
  })),
}));

function renderDialog() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ProfileSurveyDialog />
    </QueryClientProvider>
  );
}

async function pickOption(label: RegExp, option: string) {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: label }));
  fireEvent.click(await screen.findByRole('option', { name: option }));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockUpdateUserSettings.mockResolvedValue({});
  mockSettings = { onboarding: { profile_survey_pending: true } };
});

describe('ProfileSurveyDialog', () => {
  it('stays closed without the pending flag', () => {
    mockSettings = { onboarding: {} };
    renderDialog();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('keeps Save disabled until a role is picked', async () => {
    renderDialog();
    const save = screen.getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();

    await pickOption(/your role/i, 'Data Scientist');
    expect(save).toBeEnabled();
  });

  it('saves answers, including "Other" text, and clears the flag in one call', async () => {
    renderDialog();
    await pickOption(/your role/i, 'Other');
    fireEvent.change(screen.getByRole('textbox', { name: 'Your role' }), {
      target: { value: 'Prompt engineer' },
    });
    await pickOption(/hear about rhesis/i, 'GitHub');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockUpdateUserSettings).toHaveBeenCalledWith({
        onboarding: {
          profile_survey_pending: false,
          profile: {
            job_role: 'other',
            job_role_other: 'Prompt engineer',
            referral_source: 'github',
            referral_source_other: null,
          },
        },
      })
    );
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
  });

  it('skipping clears the flag without saving answers', async () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));

    await waitFor(() =>
      expect(mockUpdateUserSettings).toHaveBeenCalledWith({
        onboarding: { profile_survey_pending: false },
      })
    );
  });

  it('stays open and shows an error when saving fails', async () => {
    mockUpdateUserSettings.mockRejectedValue(new Error('boom'));
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));

    await waitFor(() => expect(mockShow).toHaveBeenCalled());
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
