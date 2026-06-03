import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ConnectedToolCard } from '../ToolCard';
import type { Tool, TypeLookup } from '@/utils/api-client/interfaces/tool';

jest.mock('@/components/common/EntityCard', () => ({
  __esModule: true,
  default: ({
    title,
    description,
    onDelete,
    chipSections,
  }: {
    title: string;
    description?: string;
    onDelete?: () => void;
    chipSections?: Array<{
      label?: string;
      chips: Array<{ key: string; label: string }>;
    }>;
  }) => (
    <div data-testid="entity-card">
      <h3>{title}</h3>
      <p>{description}</p>
      {chipSections?.map((section, idx) => (
        <div
          key={section.label ?? `section-${idx}`}
          data-testid={`chip-section-${(section.label ?? `section-${idx}`).toLowerCase()}`}
        >
          {section.chips.map(chip => (
            <span key={chip.key} data-testid={`chip-${chip.key}`}>
              {chip.label}
            </span>
          ))}
        </div>
      ))}
      {onDelete && (
        <button aria-label="delete tool" onClick={onDelete}>
          delete
        </button>
      )}
    </div>
  ),
}));

function makeTool(overrides: Partial<Tool> = {}): Tool {
  return {
    id: 'tool-1',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
    name: 'My Notion',
    description: 'Notion workspace',
    tool_provider_type_id: 'pt-1',
    tool_provider_type: {
      id: 'pt-1',
      type_name: 'ToolProviderType',
      type_value: 'notion',
    },
    ...overrides,
  } as unknown as Tool;
}

describe('ConnectedToolCard', () => {
  it('renders the tool name and description', () => {
    render(<ConnectedToolCard tool={makeTool()} onDelete={jest.fn()} />);
    expect(screen.getByText('My Notion')).toBeInTheDocument();
    expect(screen.getByText('Notion workspace')).toBeInTheDocument();
  });

  it('renders a capitalized provider chip', () => {
    render(<ConnectedToolCard tool={makeTool()} onDelete={jest.fn()} />);
    const section = screen.getByTestId('chip-section-provider');
    expect(section).toHaveTextContent('Notion');
  });

  it('renders the repository chip for github tools', () => {
    const tool = makeTool({
      name: 'My Repo',
      tool_provider_type: {
        id: 'pt-2' as TypeLookup['id'],
        type_name: 'ToolProviderType',
        type_value: 'github',
      },
      tool_metadata: { repository: { full_name: 'owner/repo' } },
    });
    render(<ConnectedToolCard tool={tool} onDelete={jest.fn()} />);
    expect(screen.getByTestId('chip-repo')).toHaveTextContent('owner/repo');
  });

  it('calls onDelete with the tool when delete is triggered', async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const tool = makeTool();
    render(<ConnectedToolCard tool={tool} onDelete={onDelete} />);

    await user.click(screen.getByRole('button', { name: /delete tool/i }));
    expect(onDelete).toHaveBeenCalledWith(tool);
  });
});
