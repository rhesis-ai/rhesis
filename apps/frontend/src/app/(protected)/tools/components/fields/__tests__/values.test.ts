import type { Tool } from '@/utils/api-client/interfaces/tool';
import type {
  ToolProvider,
  ToolProviderField,
} from '@/utils/api-client/interfaces/tool-provider';
import {
  MASKED,
  buildCredentials,
  buildMetadata,
  emptyValues,
  hydrateValues,
  missingRequired,
  visibleFields,
} from '../values';

const field = (
  key: string,
  store: 'credentials' | 'metadata',
  overrides: Partial<ToolProviderField> = {}
): ToolProviderField => ({
  key,
  label: key,
  store,
  required: true,
  secret: false,
  preserve_on_update: false,
  placeholder: '',
  help_text: '',
  help_url: '',
  ...overrides,
});

const provider = (key: string, fields: ToolProviderField[]): ToolProvider => ({
  key,
  display_name: key,
  description: '',
  auth_methods: [
    { kind: 'api_token', label: 'API token', help_url: '', available: true },
  ],
  fields,
  actions: ['test_connection'],
});

// Shapes taken from the real manifests in
// apps/backend/.../services/tool/providers/.
const NOTION = provider('notion', [
  field('NOTION_TOKEN', 'credentials', { secret: true }),
]);

const GITHUB = provider('github', [
  field('GITHUB_PERSONAL_ACCESS_TOKEN', 'credentials', { secret: true }),
  field('repository.owner', 'metadata', { required: false }),
  field('repository.repo', 'metadata', { required: false }),
]);

const GITLAB = provider('gitlab', [
  field('GITLAB_PERSONAL_ACCESS_TOKEN', 'credentials', { secret: true }),
  field('GITLAB_API_URL', 'credentials', {
    required: false,
    preserve_on_update: true,
  }),
  field('project.namespace', 'metadata'),
]);

const AZURE = provider('azure_devops', [
  field('AZURE_DEVOPS_ORG', 'credentials', { preserve_on_update: true }),
  field('AZURE_DEVOPS_EMAIL', 'credentials', { preserve_on_update: true }),
  field('AZURE_DEVOPS_PAT', 'credentials', { secret: true }),
  field('project', 'metadata'),
]);

const ASANA = provider('asana', [
  field('ASANA_ACCESS_TOKEN', 'credentials', { secret: true }),
  field('workspace_gid', 'metadata', { required: false }),
]);

const asTool = (metadata: Record<string, unknown>): Tool =>
  ({ id: 't-1', name: 'x', tool_metadata: metadata }) as unknown as Tool;

describe('visibleFields', () => {
  it('folds the fields an adapter owns into one input', () => {
    // One pasted URL fills both repository.owner and repository.repo, so the
    // form must not ask for them separately.
    const keys = visibleFields(GITHUB).map(f => f.key);

    expect(keys).toEqual(['GITHUB_PERSONAL_ACCESS_TOKEN', 'repository.owner']);
  });

  it('leaves providers without adapters alone', () => {
    expect(visibleFields(GITLAB).map(f => f.key)).toEqual([
      'GITLAB_PERSONAL_ACCESS_TOKEN',
      'GITLAB_API_URL',
      'project.namespace',
    ]);
  });
});

describe('hydrateValues', () => {
  it('masks credentials and hydrates metadata', () => {
    // Credentials are encrypted and never returned, so the form cannot show
    // them; metadata comes back and does.
    const values = hydrateValues(
      GITLAB,
      asTool({ project: { namespace: 'my-group/my-project' } })
    );

    expect(values.GITLAB_PERSONAL_ACCESS_TOKEN).toBe(MASKED);
    expect(values.GITLAB_API_URL).toBe(MASKED);
    expect(values['project.namespace']).toBe('my-group/my-project');
  });

  it('rebuilds the GitHub repository URL from the stored owner and repo', () => {
    const values = hydrateValues(
      GITHUB,
      asTool({
        repository: { owner: 'acme', repo: 'docs', full_name: 'acme/docs' },
      })
    );

    expect(values['repository.owner']).toBe('https://github.com/acme/docs');
  });

  it('leaves metadata blank when the tool has none', () => {
    const values = hydrateValues(GITHUB, asTool({}));

    expect(values['repository.owner']).toBe('');
  });
});

describe('buildCredentials', () => {
  it('omits masked and blank values so stored ones survive', () => {
    // Sending "" would read as a deliberate blank; omitting lets the backend
    // keep a preserve_on_update field.
    const credentials = buildCredentials(AZURE, {
      AZURE_DEVOPS_ORG: MASKED,
      AZURE_DEVOPS_EMAIL: '  ',
      AZURE_DEVOPS_PAT: 'new-pat',
      project: 'Contoso',
    });

    expect(credentials).toEqual({ AZURE_DEVOPS_PAT: 'new-pat' });
  });

  it('appends the GitLab API path when the user gives a bare host', () => {
    const credentials = buildCredentials(GITLAB, {
      GITLAB_PERSONAL_ACCESS_TOKEN: 'glpat-x',
      GITLAB_API_URL: 'gitlab.example.com',
      'project.namespace': 'g/p',
    });

    expect(credentials.GITLAB_API_URL).toBe(
      'https://gitlab.example.com/api/v4'
    );
  });

  it('does not double up an API path the user already supplied', () => {
    const credentials = buildCredentials(GITLAB, {
      GITLAB_PERSONAL_ACCESS_TOKEN: 'glpat-x',
      GITLAB_API_URL: 'https://gitlab.example.com/api/v4',
    });

    expect(credentials.GITLAB_API_URL).toBe(
      'https://gitlab.example.com/api/v4'
    );
  });

  it.each([
    ['https://dev.azure.com/acme', 'acme'],
    ['https://dev.azure.com/acme/', 'acme'],
    ['acme.visualstudio.com', 'acme'],
    ['acme', 'acme'],
  ])('reduces the Azure DevOps org %s to %s', (input, expected) => {
    const credentials = buildCredentials(AZURE, {
      AZURE_DEVOPS_ORG: input,
      AZURE_DEVOPS_EMAIL: 'e@x.com',
      AZURE_DEVOPS_PAT: 'pat',
    });

    expect(credentials.AZURE_DEVOPS_ORG).toBe(expected);
  });
});

describe('buildMetadata', () => {
  it.each([
    ['https://github.com/acme/docs', { owner: 'acme', repo: 'docs' }],
    ['acme/docs', { owner: 'acme', repo: 'docs' }],
    ['https://github.com/acme/docs.git', { owner: 'acme', repo: 'docs' }],
  ])('parses the repository input %s', (input, expected) => {
    const { metadata, error } = buildMetadata(GITHUB, {
      'repository.owner': input,
    });

    expect(error).toBeUndefined();
    expect(metadata.repository).toMatchObject(expected);
  });

  it('keeps full_name, which nothing declares but the tool card reads', () => {
    const { metadata } = buildMetadata(GITHUB, {
      'repository.owner': 'acme/docs',
    });

    expect(metadata.repository).toMatchObject({ full_name: 'acme/docs' });
  });

  it('reports an unparseable repository instead of sending it', () => {
    const { error } = buildMetadata(GITHUB, {
      'repository.owner': 'not a repo',
    });

    expect(error).toMatch(/invalid repository url/i);
  });

  it.each([
    ['my-group/my-project', 'my-group/my-project'],
    ['https://gitlab.com/my-group/my-project', 'my-group/my-project'],
    ['https://gitlab.com/g/p/-/tree/main/docs', 'g/p'],
    ['group/sub/project', 'group/sub/project'],
  ])('parses the GitLab project input %s', (input, expected) => {
    const { metadata, error } = buildMetadata(GITLAB, {
      'project.namespace': input,
    });

    expect(error).toBeUndefined();
    expect(metadata.project).toEqual({ namespace: expected });
  });

  it('rejects a GitLab project with no namespace', () => {
    const { error } = buildMetadata(GITLAB, { 'project.namespace': 'noslash' });

    expect(error).toMatch(/invalid project path/i);
  });

  it('omits a blank optional scope rather than sending it empty', () => {
    // A cleared workspace means "all workspaces", not an invalid value.
    const { metadata } = buildMetadata(ASANA, { workspace_gid: '   ' });

    expect(metadata).toEqual({});
  });

  it('writes a flat metadata field as-is', () => {
    const { metadata } = buildMetadata(AZURE, { project: ' Contoso ' });

    expect(metadata).toEqual({ project: 'Contoso' });
  });
});

describe('missingRequired', () => {
  it('names the fields still to fill in', () => {
    expect(missingRequired(GITLAB, emptyValues(GITLAB))).toEqual([
      'GITLAB_PERSONAL_ACCESS_TOKEN',
      'project.namespace',
    ]);
  });

  it('counts a masked credential as filled', () => {
    // Untouched means "keep what is stored", not "missing".
    const values = hydrateValues(
      GITLAB,
      asTool({ project: { namespace: 'g/p' } })
    );

    expect(missingRequired(GITLAB, values)).toEqual([]);
  });

  it('ignores optional fields', () => {
    expect(missingRequired(ASANA, { ASANA_ACCESS_TOKEN: 'x' })).toEqual([]);
  });
});

describe('round trip from a saved tool', () => {
  it.each([
    [
      'gitlab',
      GITLAB,
      { project: { namespace: 'my-group/my-project' } },
      { project: { namespace: 'my-group/my-project' } },
    ],
    [
      'github',
      GITHUB,
      { repository: { owner: 'acme', repo: 'docs', full_name: 'acme/docs' } },
      { repository: { owner: 'acme', repo: 'docs', full_name: 'acme/docs' } },
    ],
    ['asana', ASANA, { workspace_gid: '123' }, { workspace_gid: '123' }],
    ['azure_devops', AZURE, { project: 'Contoso' }, { project: 'Contoso' }],
  ])(
    'opening a saved %s tool and saving it unchanged preserves its metadata',
    (_name, manifest, stored, expected) => {
      // The failure this guards against is an edit that silently drops scope
      // the user never touched.
      const values = hydrateValues(manifest, asTool(stored));
      const { metadata, error } = buildMetadata(manifest, values);

      expect(error).toBeUndefined();
      expect(metadata).toEqual(expected);
    }
  );

  it('sends no credentials when the user edits nothing', () => {
    const values = hydrateValues(AZURE, asTool({ project: 'Contoso' }));

    expect(buildCredentials(AZURE, values)).toEqual({});
  });

  it('sends only the credential the user actually changed', () => {
    const values = hydrateValues(AZURE, asTool({ project: 'Contoso' }));
    values.AZURE_DEVOPS_PAT = 'rotated-pat';

    expect(buildCredentials(AZURE, values)).toEqual({
      AZURE_DEVOPS_PAT: 'rotated-pat',
    });
  });

  it('creates a new connection from empty values', () => {
    const values = { ...emptyValues(NOTION), NOTION_TOKEN: 'ntn_abc' };

    expect(buildCredentials(NOTION, values)).toEqual({
      NOTION_TOKEN: 'ntn_abc',
    });
    expect(buildMetadata(NOTION, values).metadata).toEqual({});
  });
});
