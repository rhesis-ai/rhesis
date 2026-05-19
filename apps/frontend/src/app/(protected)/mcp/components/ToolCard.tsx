import React from 'react';
import { IconButton } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface ConnectedToolCardProps {
  tool: Tool;
  /** Called when the edit icon is clicked — receives the originating mouse event for stopPropagation */
  onEdit: (tool: Tool, e: React.MouseEvent) => void;
  /** Called when delete is confirmed — EntityCard handles stopPropagation internally */
  onDelete: (tool: Tool) => void;
}

export function ConnectedToolCard({
  tool,
  onEdit,
  onDelete,
}: ConnectedToolCardProps) {
  const theme = useTheme();
  const providerName = tool.tool_provider_type?.type_value || 'Unknown';
  const providerIcon = MCP_PROVIDER_ICONS[providerName] ?? (
    <SmartToyIcon sx={{ fontSize: theme.iconSizes?.medium }} />
  );

  // Chip sections: provider + metadata
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
        label: tool.tool_metadata.repository.full_name,
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

  const topRightActions = (
    <IconButton
      size="small"
      onClick={e => onEdit(tool, e)}
      sx={{
        padding: '2px',
        '& .MuiSvgIcon-root': {
          fontSize: theme.typography.caption?.fontSize ?? '0.75rem',
          color: 'currentColor',
        },
      }}
    >
      <EditIcon fontSize="inherit" />
    </IconButton>
  );

  return (
    <EntityCard
      icon={providerIcon}
      title={tool.name}
      description={tool.description}
      onDelete={() => onDelete(tool)}
      topRightActions={topRightActions}
      chipSections={chipSections}
    />
  );
}
