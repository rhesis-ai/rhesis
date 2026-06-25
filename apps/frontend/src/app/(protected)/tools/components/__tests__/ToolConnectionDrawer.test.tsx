import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ToolConnectionDrawer } from '../ToolConnectionDrawer';
import type { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import type { Tool } from '@/utils/api-client/interfaces/tool';

const mockTestToolConnection = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: {
      session_token: 'tok',
      user: { email: 'user@example.com' },
    },
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getServicesClient: () => ({
      testToolConnection: mockTestToolConnection,
    }),
  })),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/config/tool-providers', () => ({
  TOOL_PROVIDER_ICONS: {},
  formatToolProviderDisplayName: (typeValue: string) =>
    typeValue.charAt(0).toUpperCase() + typeValue.slice(1),
}));

// Mock BaseDrawer so we can assert on title, save button state, and close.
jest.mock('@/components/common/BaseDrawer', () => ({
  __esModule: true,
  default: ({
    open,
    title,
    children,
    onClose,
    onSave,
    saveDisabled,
    saveButtonText,
  }: {
    open: boolean;
    title: string;
    children: React.ReactNode;
    onClose: () => void;
    onSave: () => void;
    saveDisabled?: boolean;
    saveButtonText?: string;
  }) =>
    open ? (
      <div data-testid="base-drawer">
        <h2>{title}</h2>
        {children}
        <button onClick={onClose}>cancel</button>
        <button onClick={onSave} disabled={saveDisabled}>
          {saveButtonText}
        </button>
      </div>
    ) : null,
}));

const notionProvider: TypeLookup = {
  id: 'pt-1' as TypeLookup['id'],
  type_name: 'ToolProviderType',
  type_value: 'notion',
};

const asanaProvider: TypeLookup = {
  id: 'pt-asana' as TypeLookup['id'],
  type_name: 'ToolProviderType',
  type_value: 'asana',
};

function renderDrawer(props = {}) {
  const onClose = jest.fn();
  const onConnect = jest.fn().mockResolvedValue({ id: 'tool-1' });
  render(
    <ToolConnectionDrawer
      open
      provider={notionProvider}
      mode="create"
      onClose={onClose}
      onConnect={onConnect}
      {...props}
    />
  );
  return { onClose, onConnect };
}

describe('ToolConnectionDrawer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockTestToolConnection.mockResolvedValue({
      is_authenticated: 'Yes',
      message: 'Token is valid',
    });
  });

  it('renders the connect title for the selected provider', () => {
    renderDrawer();
    expect(screen.getByText('Connect Notion')).toBeInTheDocument();
  });

  it('renders the connection name and auth token fields', () => {
    renderDrawer();
    expect(screen.getByLabelText(/connection name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/authentication token/i)).toBeInTheDocument();
  });

  it('calls onClose when cancel is clicked', async () => {
    const user = userEvent.setup();
    const { onClose } = renderDrawer();
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('disables Test Connection until an auth token is entered', async () => {
    const user = userEvent.setup();
    renderDrawer();

    const testButton = screen.getByRole('button', { name: /test connection/i });
    expect(testButton).toBeDisabled();

    await user.type(screen.getByLabelText(/authentication token/i), 'secret');
    expect(testButton).toBeEnabled();
  });

  it('calls testToolConnection with provider id and credentials', async () => {
    const user = userEvent.setup();
    renderDrawer();

    await user.type(screen.getByLabelText(/authentication token/i), 'secret');
    await user.click(screen.getByRole('button', { name: /test connection/i }));

    await waitFor(() => {
      expect(mockTestToolConnection).toHaveBeenCalledWith(
        expect.objectContaining({
          provider_type_id: 'pt-1',
          credentials: { NOTION_TOKEN: 'secret' },
        })
      );
    });
    expect(await screen.findByText('Token is valid')).toBeInTheDocument();
  });

  it('does not pre-select a provider when adding a new tool', () => {
    render(
      <ToolConnectionDrawer
        open
        providers={[asanaProvider, notionProvider]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    expect(screen.getByText('Add tool connection')).toBeInTheDocument();
    expect(screen.queryByLabelText(/connection name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/workspace gid/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/provider/i)).toHaveTextContent(
      /select a provider/i
    );
  });

  it('shows provider-specific fields after choosing a provider', async () => {
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[asanaProvider, notionProvider]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByLabelText(/provider/i));
    await user.click(screen.getByRole('option', { name: /notion/i }));

    expect(screen.getByText('Connect Notion')).toBeInTheDocument();
    expect(screen.getByLabelText(/connection name/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/workspace gid/i)).not.toBeInTheDocument();
  });

  it('uses the tool provider in edit mode instead of a stale create selection', () => {
    const notionTool: Tool = {
      id: 'tool-1' as Tool['id'],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      name: 'sgsr',
      description: 'sgpjwgwpirgjwrgo',
      tool_provider_type_id: notionProvider.id,
      tool_provider_type: notionProvider,
    };

    const { rerender } = render(
      <ToolConnectionDrawer
        open
        providers={[asanaProvider, notionProvider]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );
    expect(screen.getByText('Add tool connection')).toBeInTheDocument();

    rerender(
      <ToolConnectionDrawer
        open
        providers={[asanaProvider, notionProvider]}
        tool={notionTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    expect(screen.getByText('Update Notion')).toBeInTheDocument();
    expect(screen.queryByLabelText(/workspace gid/i)).not.toBeInTheDocument();
  });
});
