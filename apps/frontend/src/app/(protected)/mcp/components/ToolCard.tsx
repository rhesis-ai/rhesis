import React from 'react';
import { useTheme } from '@mui/material/styles';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface ConnectedToolCardProps {
  tool: Tool;
  /** Called when delete is confirmed — EntityCard handles stopPropagation internally */
  onDelete: (tool: Tool) => void;
}

export function ConnectedToolCard({ tool, onDelete }: ConnectedToolCardProps) {
  const theme = useTheme();
  const providerName = tool.tool_provider_type?.type_value || 'Unknown';
  const providerIcon = MCP_PROVIDER_ICONS[providerName] ?? (
    <SmartToyIcon sx={{ fontSize: theme.iconSizes?.medium }} />
  );

  const chipSections: ChipSection[] = [];

  if (providerName && providerName !== 'Unknown') {
    const providerChips: { key: string; label: string }[] = [
      {
        key: 'provider',
        label: providerName.charAt(0).toUpperCase() + providerName.slice(1),
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
      chipSections={chipSections}
    />
  );
}
