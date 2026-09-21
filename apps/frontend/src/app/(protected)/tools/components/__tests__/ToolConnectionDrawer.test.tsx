import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ToolConnectionDrawer } from '../ToolConnectionDrawer';
import type { Tool, TypeLookup } from '@/utils/api-client/interfaces/tool';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';

const mockTestToolConnection = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { email: 'user@example.com' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getServicesClient: () => ({ testToolConnection: mockTestToolConnection }),
  })),
}));

jest.mock('@/config/tool-providers', () => ({
  TOOL_PROVIDER_ICONS: {},
  formatToolProviderDisplayName: (typeValue: string) =>
    typeValue.charAt(0).toUpperCase() + typeValue.slice(1),
}));

// Shapes copied from the real manifests, so the form under test is driven by
// the same data the backend serves.
const NOTION: ToolProvider = {
  key: 'notion',
  display_name: 'Notion',
  description: 'Pull pages into your knowledge base',
  auth_methods: [
    { kind: 'api_token', label: 'Token', help_url: '', available: true },
  ],
  fields: [
    {
      key: 'NOTION_TOKEN',
      label: 'Integration token',
      store: 'credentials',
      required: true,
      secret: true,
      preserve_on_update: false,
      placeholder: '',
      help_text: '',
      help_url: '',
    },
  ],
  actions: ['extract', 'test_connection'],
};

const GITLAB: ToolProvider = {
  key: 'gitlab',
  display_name: 'GitLab',
  description: 'Import issues and merge requests',
  auth_methods: [
    { kind: 'api_token', label: 'Token', help_url: '', available: true },
  ],
  fields: [
    {
      key: 'GITLAB_PERSONAL_ACCESS_TOKEN',
      label: 'Personal access token',
      store: 'credentials',
      required: true,
      secret: true,
      preserve_on_update: false,
      placeholder: '',
      help_text: '',
      help_url: '',
    },
    {
      key: 'GITLAB_API_URL',
      label: 'GitLab API URL',
      store: 'credentials',
      required: false,
      secret: false,
      preserve_on_update: true,
      placeholder: '',
      help_text: '',
      help_url: '',
    },
    {
      key: 'project.namespace',
      label: 'Project',
      store: 'metadata',
      required: true,
      secret: false,
      preserve_on_update: false,
      placeholder: 'my-group/my-project',
      help_text: '',
      help_url: '',
    },
  ],
  actions: ['extract', 'test_connection'],
};

jest.mock('@/hooks/useToolProviders', () => ({
  useToolProviders: () => ({
    data: mockProviders,
    isLoading: false,
  }),
}));

let mockProviders: ToolProvider[] = [];

jest.mock('@/components/common/BaseDrawer', () => ({
  __esModule: true,
  default: ({
    open,
    title,
    children,
    onSave,
    saveDisabled,
    saveButtonText,
    error,
  }: {
    open: boolean;
    title: string;
    children: React.ReactNode;
    onSave: () => void;
    saveDisabled?: boolean;
    saveButtonText?: string;
    error?: string;
  }) =>
    open ? (
      <div data-testid="base-drawer">
        <h2>{title}</h2>
        {error ? <div role="alert">{error}</div> : null}
        {children}
        <button onClick={onSave} disabled={saveDisabled}>
          {saveButtonText}
        </button>
      </div>
    ) : null,
}));

const lookup = (id: string, typeValue: string) =>
  ({ id, type_value: typeValue }) as unknown as TypeLookup;

const notionLookup = lookup('pt-notion', 'notion');
const gitlabLookup = lookup('pt-gitlab', 'gitlab');

beforeEach(() => {
  jest.clearAllMocks();
  mockProviders = [NOTION, GITLAB];
  mockTestToolConnection.mockResolvedValue({
    is_authenticated: 'Yes',
    message: 'Token is valid',
  });
});

describe('creating a connection', () => {
  it('shows the provider grid and no form until one is chosen', () => {
    render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup, gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    expect(screen.getByText('Add tool connection')).toBeInTheDocument();
    expect(screen.queryByLabelText(/connection name/i)).not.toBeInTheDocument();
  });

  it('renders the chosen provider fields from its manifest', async () => {
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup, gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'GitLab' }));

    expect(screen.getByText('Connect GitLab')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Personal access token/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^GitLab API URL/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Project/)).toBeInTheDocument();
  });

  it('collapses the grid once a provider is chosen', async () => {
    // Nine tiles above the form buries the fields the user came to fill in.
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup, gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Notion' }));

    expect(
      screen.queryByRole('radio', { name: 'GitLab' })
    ).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /change/i })).toBeInTheDocument();
  });

  it('brings the grid back, keeping the name but clearing the fields', async () => {
    // Name and description are provider-agnostic; credentials are not.
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup, gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Notion' }));
    await user.type(screen.getByLabelText(/connection name/i), 'Docs');
    await user.type(screen.getByLabelText(/^Integration token/), 'ntn_abc');

    await user.click(screen.getByRole('button', { name: /change/i }));
    expect(screen.getByRole('radio', { name: 'GitLab' })).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'GitLab' }));

    expect(screen.getByLabelText(/connection name/i)).toHaveValue('Docs');
    expect(screen.getByLabelText(/^Personal access token/)).toHaveValue('');
  });

  it('will not save until the connection has been tested', async () => {
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Notion' }));
    await user.type(screen.getByLabelText(/connection name/i), 'Docs');
    await user.type(screen.getByLabelText(/^Integration token/), 'ntn_abc');

    expect(screen.getByRole('button', { name: 'Connect' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: /test connection/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled()
    );
  });

  it('sends the credentials and metadata the manifest describes', async () => {
    const user = userEvent.setup();
    const onConnect = jest.fn().mockResolvedValue({});
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={onConnect}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'GitLab' }));
    await user.type(screen.getByLabelText(/connection name/i), 'Internal');
    await user.type(screen.getByLabelText(/^Personal access token/), 'glpat-x');
    await user.type(screen.getByLabelText(/^Project/), 'my-group/my-project');
    await user.click(screen.getByRole('button', { name: /test connection/i }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled()
    );
    await user.click(screen.getByRole('button', { name: 'Connect' }));

    await waitFor(() => expect(onConnect).toHaveBeenCalled());
    expect(onConnect).toHaveBeenCalledWith(
      'pt-gitlab',
      expect.objectContaining({
        credentials: { GITLAB_PERSONAL_ACCESS_TOKEN: 'glpat-x' },
        tool_metadata: { project: { namespace: 'my-group/my-project' } },
      })
    );
  });

  it('reports an unparseable project instead of sending it', async () => {
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'GitLab' }));
    await user.type(screen.getByLabelText(/^Personal access token/), 'glpat-x');
    await user.type(screen.getByLabelText(/^Project/), 'noslash');
    await user.click(screen.getByRole('button', { name: /test connection/i }));

    expect(
      await screen.findByText(/invalid project path/i)
    ).toBeInTheDocument();
    expect(mockTestToolConnection).not.toHaveBeenCalled();
  });
  it('keeps what the user typed when the manifests refetch', async () => {
    // useToolProviders is a React Query hook: a refetch hands back a fresh
    // array, so the manifest object identity changes even though nothing about
    // the provider did. Reseeding on that wiped the form mid-edit.
    const user = userEvent.setup();
    const { rerender } = render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Notion' }));
    await user.type(screen.getByLabelText(/^Integration token/), 'ntn_abc');

    mockProviders = [{ ...NOTION }, { ...GITLAB }];
    rerender(
      <ToolConnectionDrawer
        open
        providers={[notionLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    expect(screen.getByLabelText(/^Integration token/)).toHaveValue('ntn_abc');
  });

  it('keeps what the user typed when the provider lookups refresh', async () => {
    // useTypeLookups starts from the server-fetched array and swaps in a fresh
    // one when its query resolves. Resetting on that array's identity wiped
    // the form mid-entry.
    const user = userEvent.setup();
    const { rerender } = render(
      <ToolConnectionDrawer
        open
        providers={[notionLookup]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Notion' }));
    await user.type(screen.getByLabelText(/connection name/i), 'Docs');
    await user.type(screen.getByLabelText(/^Integration token/), 'ntn_abc');

    // Same contents, new array and new object identities.
    rerender(
      <ToolConnectionDrawer
        open
        providers={[lookup('pt-notion', 'notion')]}
        mode="create"
        onClose={jest.fn()}
        onConnect={jest.fn()}
      />
    );

    expect(screen.getByLabelText(/connection name/i)).toHaveValue('Docs');
    expect(screen.getByLabelText(/^Integration token/)).toHaveValue('ntn_abc');
  });
});

describe('editing a connection', () => {
  const savedTool = {
    id: 'tool-1',
    name: 'Internal tooling',
    description: 'Wiki pages',
    tool_provider_type: gitlabLookup,
    tool_metadata: { project: { namespace: 'my-group/my-project' } },
  } as unknown as Tool;

  it('hydrates the scope and masks the credentials', async () => {
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Project/)).toHaveValue(
        'my-group/my-project'
      )
    );
    // Credentials are encrypted and never returned, so the form shows a mask.
    expect(screen.getByLabelText(/^Personal access token/)).toHaveValue(
      '************'
    );
  });

  it('tests against the saved tool when no credential was re-entered', async () => {
    const user = userEvent.setup();
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Project/)).toHaveValue(
        'my-group/my-project'
      )
    );
    await user.click(screen.getByRole('button', { name: /test connection/i }));

    // Sending the tool id lets the backend fill the rest from what is stored,
    // so the user does not have to retype a token to change the scope.
    await waitFor(() =>
      expect(mockTestToolConnection).toHaveBeenCalledWith(
        expect.objectContaining({ tool_id: 'tool-1' })
      )
    );
  });

  it('sends only the credential the user actually changed', async () => {
    const user = userEvent.setup();
    const onUpdate = jest.fn().mockResolvedValue(undefined);
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={onUpdate}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Personal access token/)).toHaveValue(
        '************'
      )
    );

    const token = screen.getByLabelText(/^Personal access token/);
    await user.click(token);
    await user.type(token, 'glpat-new');
    await user.click(screen.getByRole('button', { name: /test connection/i }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Update' })).toBeEnabled()
    );
    await user.click(screen.getByRole('button', { name: 'Update' }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    // The untouched API URL is omitted so the backend keeps the stored value.
    expect(onUpdate).toHaveBeenCalledWith(
      'tool-1',
      expect.objectContaining({
        credentials: { GITLAB_PERSONAL_ACCESS_TOKEN: 'glpat-new' },
      })
    );
  });

  it('offers no provider picker or change control', async () => {
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Project/)).toHaveValue(
        'my-group/my-project'
      )
    );
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /change/i })
    ).not.toBeInTheDocument();
  });

  it('shows no test prompt until something actually changes', async () => {
    // An Alert with no content still draws its box, so an untouched edit form
    // showed an empty blue panel.
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Project/)).toHaveValue(
        'my-group/my-project'
      )
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('does not offer to save when nothing has changed', async () => {
    render(
      <ToolConnectionDrawer
        open
        providers={[gitlabLookup]}
        tool={savedTool}
        mode="edit"
        onClose={jest.fn()}
        onUpdate={jest.fn()}
      />
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/^Project/)).toHaveValue(
        'my-group/my-project'
      )
    );
    expect(screen.getByRole('button', { name: 'Update' })).toBeDisabled();
  });
});
