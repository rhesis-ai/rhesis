import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { QueryClient } from '@tanstack/react-query';

import ModelsPageClient, {
  type ModelsPageInitialData,
} from '../ModelsPageClient';
import type { Model } from '@/utils/api-client/interfaces/model';
import type { UserSettings } from '@/utils/api-client/interfaces/user';
import { userSettingsKeys } from '@/constants/query-keys';

const mockRefreshFeatures = jest.fn();
const mockDeleteModel = jest.fn();
const mockFetchUserSettings = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1', email: 'a@b.c' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/contexts/FeaturesContext', () => ({
  useRefreshFeatures: () => mockRefreshFeatures,
  useRhesisKeyEnabled: () => false,
}));

jest.mock('@/contexts/OrganizationContext', () => ({
  useOrganization: () => ({ organization: null }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/hooks/useCreateModel', () => ({
  useCreateModel: () => jest.fn(),
}));

jest.mock('@/hooks/useUserSettings', () => ({
  fetchUserSettings: (...args: unknown[]) => mockFetchUserSettings(...args),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getModelsClient: () => ({
      deleteModel: mockDeleteModel,
      testModelConnection: jest.fn().mockResolvedValue({ status: 'success' }),
    }),
  })),
}));

// Page chrome and drawers are not under test; the card and the confirm modal
// are reduced to the one control each that the delete flow needs.
jest.mock('@/components/layout/PageLayout', () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
jest.mock('@/components/common/Fab', () => ({
  Fab: () => null,
  FabAddIcon: () => null,
  FabGroup: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('@/components/common/GridToolbar', () => ({
  __esModule: true,
  default: () => null,
  ToolbarPillTabs: () => null,
  directoryToolbarProps: {},
}));
jest.mock('@/components/common/PolyphemusAccessModal', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('../ModelConnectionDrawer', () => ({
  ModelConnectionDrawer: () => null,
}));
jest.mock('../ModelFilterDrawer', () => ({
  __esModule: true,
  default: () => null,
  EMPTY_MODEL_FILTERS: { providers: [], status: '' },
  hasActiveModelFilters: () => false,
  countActiveModelFilters: () => 0,
}));
jest.mock('../index', () => ({
  PlatformKeyDrawer: () => null,
  ConnectedModelCard: ({
    model,
    userSettings,
    onDelete,
  }: {
    model: { id: string; name: string };
    userSettings?: { models?: { generation?: { model_id?: string } } } | null;
    onDelete?: (model: unknown) => void;
  }) => (
    <div>
      <span>{model.name}</span>
      {userSettings?.models?.generation?.model_id === model.id && (
        <span>default: {model.name}</span>
      )}
      <button onClick={() => onDelete?.(model)}>delete {model.name}</button>
    </div>
  ),
}));
jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: ({
    open,
    onConfirm,
  }: {
    open: boolean;
    onConfirm: () => void;
  }) => (open ? <button onClick={onConfirm}>confirm delete</button> : null),
}));

const MODEL = {
  id: 'model-1',
  name: 'My model',
  model_name: 'gpt',
  model_type: 'language',
} as unknown as Model;

const OTHER_MODEL = {
  ...MODEL,
  id: 'model-2',
  name: 'Other model',
} as unknown as Model;

const settingsWithDefault = (modelId: string) =>
  ({
    models: { generation: { model_id: modelId } },
  }) as unknown as UserSettings;

const INITIAL_DATA: ModelsPageInitialData = {
  models: [MODEL],
  providerTypes: [],
  userSettings: null,
  statuses: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  mockDeleteModel.mockResolvedValue(undefined);
  mockFetchUserSettings.mockResolvedValue(null);
});

describe('ModelsPageClient', () => {
  it('refetches features after a model is deleted', async () => {
    render(<ModelsPageClient initialData={INITIAL_DATA} />);

    await userEvent.click(
      screen.getByRole('button', { name: 'delete My model' })
    );
    expect(mockRefreshFeatures).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole('button', { name: 'confirm delete' })
    );

    await waitFor(() => expect(mockRefreshFeatures).toHaveBeenCalledTimes(1));
    expect(mockDeleteModel).toHaveBeenCalledWith('model-1');
    expect(screen.queryByText('My model')).not.toBeInTheDocument();
  });

  it('shows the default the backend moved to after the default is deleted', async () => {
    const invalidate = jest.spyOn(QueryClient.prototype, 'invalidateQueries');
    mockFetchUserSettings.mockResolvedValue(settingsWithDefault('model-2'));
    render(
      <ModelsPageClient
        initialData={{
          ...INITIAL_DATA,
          models: [MODEL, OTHER_MODEL],
          userSettings: settingsWithDefault('model-1'),
        }}
      />
    );
    expect(screen.getByText('default: My model')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'delete My model' })
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'confirm delete' })
    );

    expect(await screen.findByText('default: Other model')).toBeInTheDocument();
    // The cached settings are dropped first, or the fetch would return them.
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: userSettingsKeys.all('user-1'),
    });
    expect(mockRefreshFeatures).toHaveBeenCalledTimes(1);
    invalidate.mockRestore();
  });

  it('does not refetch features when the delete fails', async () => {
    mockDeleteModel.mockRejectedValue(new Error('nope'));
    render(<ModelsPageClient initialData={INITIAL_DATA} />);

    await userEvent.click(
      screen.getByRole('button', { name: 'delete My model' })
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'confirm delete' })
    );

    expect(await screen.findByText('nope')).toBeInTheDocument();
    expect(mockRefreshFeatures).not.toHaveBeenCalled();
  });
});
