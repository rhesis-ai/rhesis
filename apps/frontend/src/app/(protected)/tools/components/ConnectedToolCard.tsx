import React from 'react';
import { useTheme } from '@mui/material/styles';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EntityCard, { skeletonCardKeys } from '@/components/common/EntityCard';
import { Tool } from '@/utils/api-client/interfaces/tool';
import {
  TOOL_PROVIDER_ICONS,
  formatToolProviderDisplayName,
} from '@/config/tool-providers';

interface ConnectedToolCardProps {
  tool: Tool;
  onDelete: (tool: Tool) => void;
  onCardClick?: (tool: Tool) => void;
}

export function ConnectedToolCard({
  tool,
  onDelete,
  onCardClick,
}: ConnectedToolCardProps) {
  const theme = useTheme();
  const providerName = tool.tool_provider_type?.type_value || 'Unknown';
  const providerIcon = TOOL_PROVIDER_ICONS[providerName] ?? (
    <SmartToyIcon sx={{ fontSize: theme.iconSizes?.medium }} />
  );

  const hasProvider = providerName !== 'Unknown';
  // Where the tool reads from: a repository or a space.
  const context =
    providerName === 'github'
      ? (tool.tool_metadata?.repository?.full_name ?? undefined)
      : providerName === 'jira' && tool.tool_metadata?.space_key
        ? `Space: ${tool.tool_metadata.space_key}`
        : undefined;

  return (
    <EntityCard
      icon={providerIcon}
      title={tool.name}
      description={tool.description}
      onDelete={() => onDelete(tool)}
      onClick={onCardClick ? () => onCardClick(tool) : undefined}
      context={context}
      facts={
        hasProvider
          ? [
              {
                key: 'provider',
                kind: 'type',
                label: formatToolProviderDisplayName(providerName),
              },
            ]
          : []
      }
    />
  );
}

/** Typical values for a loading view's cards, only the fields the card reads. */
const PLACEHOLDER_TOOL = {
  id: '00000000-0000-0000-0000-000000000000',
  name: 'Tool connection',
  tool_provider_type: { type_value: 'github' },
  tool_metadata: { repository: { full_name: 'organization/repository' } },
} as unknown as Tool;

const noop = () => {};

/** A loading view's cards: the real card in skeleton mode. */
export function ConnectedToolCardPlaceholders() {
  return (
    <>
      {skeletonCardKeys.map(key => (
        <ConnectedToolCard key={key} tool={PLACEHOLDER_TOOL} onDelete={noop} />
      ))}
    </>
  );
}
