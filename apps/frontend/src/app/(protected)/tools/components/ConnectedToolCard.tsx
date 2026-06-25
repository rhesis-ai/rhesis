import React from 'react';
import { useTheme } from '@mui/material/styles';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
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

  const chipSections: ChipSection[] = [];

  if (providerName && providerName !== 'Unknown') {
    const providerChips: { key: string; label: string }[] = [
      {
        key: 'provider',
        label: formatToolProviderDisplayName(providerName),
      },
    ];

    if (providerName === 'github' && tool.tool_metadata?.repository) {
      providerChips.push({
        key: 'repo',
        label: tool.tool_metadata.repository.full_name ?? '',
      });
    }

    if (providerName === 'jira' && tool.tool_metadata?.space_key) {
      providerChips.push({
        key: 'space',
        label: `Space: ${tool.tool_metadata.space_key}`,
      });
    }

    chipSections.push({ label: 'Provider', chips: providerChips });
  }

  return (
    <EntityCard
      icon={providerIcon}
      title={tool.name}
      description={tool.description}
      onDelete={() => onDelete(tool)}
      onClick={onCardClick ? () => onCardClick(tool) : undefined}
      chipSections={chipSections}
    />
  );
}
