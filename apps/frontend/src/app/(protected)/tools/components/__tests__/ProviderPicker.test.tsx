import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ProviderPicker, buildProviderChoices } from '../ProviderPicker';
import type { TypeLookup } from '@/utils/api-client/interfaces/tool';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';

jest.mock('@/config/tool-providers', () => ({
  TOOL_PROVIDER_ICONS: { notion: <span data-testid="icon-notion" /> },
  formatToolProviderDisplayName: (typeValue: string) =>
    typeValue.charAt(0).toUpperCase() + typeValue.slice(1),
}));

const lookup = (id: string, typeValue: string) =>
  ({ id, type_value: typeValue }) as unknown as TypeLookup;

const manifest = (key: string, displayName: string): ToolProvider => ({
  key,
  display_name: displayName,
  description: `Connect ${displayName}`,
  auth_methods: [
    { kind: 'api_token', label: 'API token', help_url: '', available: true },
  ],
  fields: [],
  actions: ['test_connection'],
});

describe('buildProviderChoices', () => {
  it('joins lookups to manifests and sorts by display name', () => {
    const choices = buildProviderChoices(
      [lookup('id-n', 'notion'), lookup('id-a', 'asana')],
      [manifest('notion', 'Notion'), manifest('asana', 'Asana')]
    );

    expect(choices.map(c => c.displayName)).toEqual(['Asana', 'Notion']);
    expect(choices[1]).toMatchObject({ id: 'id-n', key: 'notion' });
  });

  it('drops a lookup with no manifest', () => {
    // The backend would reject a tool for a provider it does not know, so a
    // tile that cannot be connected is worse than no tile.
    const choices = buildProviderChoices(
      [lookup('id-n', 'notion'), lookup('id-x', 'retired-provider')],
      [manifest('notion', 'Notion')]
    );

    expect(choices).toHaveLength(1);
    expect(choices[0].key).toBe('notion');
  });

  it('falls back to the provider key when a manifest has no display name', () => {
    // The tile's visible text and its aria-label both read this one value, so
    // they cannot disagree.
    const nameless = { ...manifest('notion', 'Notion'), display_name: '' };
    const choices = buildProviderChoices(
      [lookup('id-n', 'notion')],
      [nameless]
    );

    expect(choices[0].displayName).toBe('Notion');
  });

  it('drops a manifest with no lookup', () => {
    // Saving needs the type_lookup UUID, so a manifest alone is not enough.
    const choices = buildProviderChoices([], [manifest('notion', 'Notion')]);

    expect(choices).toEqual([]);
  });
});

describe('ProviderPicker', () => {
  const lookups = [lookup('id-n', 'notion'), lookup('id-a', 'asana')];
  const providers = [manifest('notion', 'Notion'), manifest('asana', 'Asana')];

  it('shows every provider at once, with its description', () => {
    render(
      <ProviderPicker
        lookups={lookups}
        providers={providers}
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByRole('radio', { name: 'Notion' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Asana' })).toBeInTheDocument();
    expect(screen.getByText('Connect Notion')).toBeInTheDocument();
  });

  it('reports the chosen provider with its lookup id', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(
      <ProviderPicker
        lookups={lookups}
        providers={providers}
        onSelect={onSelect}
      />
    );

    await user.click(screen.getByRole('radio', { name: 'Asana' }));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'id-a', key: 'asana' })
    );
  });

  it('marks only the selected tile as checked', () => {
    render(
      <ProviderPicker
        lookups={lookups}
        providers={providers}
        selectedId="id-n"
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByRole('radio', { name: 'Notion' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    expect(screen.getByRole('radio', { name: 'Asana' })).toHaveAttribute(
      'aria-checked',
      'false'
    );
  });

  it('falls back to a generic icon for a provider it has no logo for', () => {
    // A backend newer than this build can serve a provider whose logo ships
    // later; the tile must still be usable rather than breaking the grid.
    render(
      <ProviderPicker
        lookups={lookups}
        providers={providers}
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByTestId('icon-notion')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Asana' })).toBeInTheDocument();
  });

  it('says so when the deployment offers no providers', () => {
    render(<ProviderPicker lookups={[]} providers={[]} onSelect={jest.fn()} />);

    expect(
      screen.getByText(/no tool providers are available/i)
    ).toBeInTheDocument();
  });

  it('shows placeholders while loading rather than an empty state', () => {
    const { container } = render(
      <ProviderPicker
        lookups={[]}
        providers={[]}
        loading
        onSelect={jest.fn()}
      />
    );

    expect(
      screen.queryByText(/no tool providers are available/i)
    ).not.toBeInTheDocument();
    expect(container.querySelectorAll('.MuiSkeleton-root').length).toBe(6);
  });

  it('shows placeholders when the lookups arrive before the manifests', () => {
    // The lookups are server-fetched and present on first render, so this is
    // the normal first paint rather than a rare race. Keying the skeleton off
    // the lookups being empty showed "no providers" on every open.
    const { container } = render(
      <ProviderPicker
        lookups={lookups}
        providers={[]}
        loading
        onSelect={jest.fn()}
      />
    );

    expect(
      screen.queryByText(/no tool providers are available/i)
    ).not.toBeInTheDocument();
    expect(container.querySelectorAll('.MuiSkeleton-root').length).toBe(6);
  });
});
