import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ProviderFields } from '../ProviderFields';
import { MASKED } from '../values';
import type {
  ToolProvider,
  ToolProviderField,
} from '@/utils/api-client/interfaces/tool-provider';

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

const GITLAB = provider('gitlab', [
  field('GITLAB_PERSONAL_ACCESS_TOKEN', 'credentials', {
    label: 'Personal access token',
    secret: true,
  }),
  field('GITLAB_API_URL', 'credentials', {
    label: 'GitLab API URL',
    required: false,
    help_text: 'Self-managed instances only.',
  }),
  field('project.namespace', 'metadata', {
    label: 'Project',
    placeholder: 'my-group/my-project',
  }),
]);

const JIRA = provider('jira', [
  field('JIRA_API_TOKEN', 'credentials', { label: 'API token', secret: true }),
  field('space_key', 'metadata', { label: 'Project key' }),
]);

const GITHUB = provider('github', [
  field('GITHUB_PERSONAL_ACCESS_TOKEN', 'credentials', {
    label: 'Personal access token',
    secret: true,
  }),
  field('repository.owner', 'metadata', {
    label: 'Repository',
    required: false,
  }),
  field('repository.repo', 'metadata', { required: false }),
]);

describe('ProviderFields', () => {
  it('renders every field the manifest declares, with its label', () => {
    render(
      <ProviderFields manifest={GITLAB} values={{}} onChange={jest.fn()} />
    );

    expect(screen.getByLabelText(/^Personal access token/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^GitLab API URL/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Project/)).toBeInTheDocument();
  });

  it('asks once for a field that an adapter splits in two', () => {
    // The repo URL fills both repository.owner and repository.repo.
    render(
      <ProviderFields manifest={GITHUB} values={{}} onChange={jest.fn()} />
    );

    expect(screen.getAllByLabelText(/^Repository/)).toHaveLength(1);
  });

  it('masks a secret and reports what the user types', async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ProviderFields manifest={GITLAB} values={{}} onChange={onChange} />
    );

    const token = screen.getByLabelText(/^Personal access token/);
    expect(token).toHaveAttribute('type', 'password');

    await user.type(token, 'g');
    expect(onChange).toHaveBeenCalledWith('GITLAB_PERSONAL_ACCESS_TOKEN', 'g');
  });

  it('clears a masked value on focus so typing replaces it', async () => {
    // Without this the user appends to a row of asterisks and sends nonsense.
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ProviderFields
        manifest={GITLAB}
        values={{ GITLAB_PERSONAL_ACCESS_TOKEN: MASKED }}
        onChange={onChange}
      />
    );

    await user.click(screen.getByLabelText(/^Personal access token/));

    expect(onChange).toHaveBeenCalledWith('GITLAB_PERSONAL_ACCESS_TOKEN', '');
  });

  it('offers no reveal button while the value is still masked', () => {
    // There is nothing to reveal: the real credential was never sent here.
    render(
      <ProviderFields
        manifest={GITLAB}
        values={{ GITLAB_PERSONAL_ACCESS_TOKEN: MASKED }}
        onChange={jest.fn()}
      />
    );

    expect(
      screen.queryByRole('button', { name: /show personal access token/i })
    ).not.toBeInTheDocument();
  });

  it('reveals a secret the user has typed', async () => {
    const user = userEvent.setup();
    render(
      <ProviderFields
        manifest={GITLAB}
        values={{ GITLAB_PERSONAL_ACCESS_TOKEN: 'glpat-x' }}
        onChange={jest.fn()}
      />
    );

    await user.click(
      screen.getByRole('button', { name: /show personal access token/i })
    );

    expect(screen.getByLabelText(/^Personal access token/)).toHaveAttribute(
      'type',
      'text'
    );
  });

  it('shows a select for a field whose options come from the provider', async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ProviderFields
        manifest={JIRA}
        values={{ space_key: '' }}
        onChange={onChange}
        options={{
          space_key: [
            { key: 'ENG', name: 'Engineering' },
            { key: 'SUP', name: 'Support' },
          ],
        }}
      />
    );

    await user.click(screen.getByLabelText(/^Project key/));
    await user.click(screen.getByRole('option', { name: 'Support' }));

    expect(onChange).toHaveBeenCalledWith('space_key', 'SUP');
  });

  it('falls back to a text box when the options are not loaded yet', () => {
    // The Jira projects arrive with the test-connection response, so before
    // that the field still has to be usable rather than an empty dropdown.
    render(<ProviderFields manifest={JIRA} values={{}} onChange={jest.fn()} />);

    expect(screen.getByLabelText(/^Project key/)).toBeInTheDocument();
  });

  it('shows help text and links out where the manifest provides them', () => {
    const withHelp = provider('x', [
      field('TOKEN', 'credentials', {
        label: 'Token',
        help_text: 'Generate one in settings.',
        help_url: 'https://example.com/tokens',
      }),
    ]);
    render(
      <ProviderFields manifest={withHelp} values={{}} onChange={jest.fn()} />
    );

    expect(screen.getByText(/generate one in settings/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /how to get this/i })
    ).toHaveAttribute('href', 'https://example.com/tokens');
  });

  it('marks required fields and leaves optional ones unmarked', () => {
    render(
      <ProviderFields manifest={GITLAB} values={{}} onChange={jest.fn()} />
    );

    expect(screen.getByLabelText(/^Personal access token/)).toBeRequired();
    expect(screen.getByLabelText(/^GitLab API URL/)).not.toBeRequired();
  });
});
