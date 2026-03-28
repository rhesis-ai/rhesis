import React from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { AddIcon } from '@/components/icons';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';

interface ConnectedToolCardProps {
  tool: Tool;
  onEdit: (tool: Tool, e: React.MouseEvent) => void;
  onDelete: (tool: Tool, e: React.MouseEvent) => void;
}

export function ConnectedToolCard({
  tool,
  onEdit,
  onDelete,
}: ConnectedToolCardProps) {
  const providerName = tool.tool_provider_type?.type_value || 'Unknown';
  const providerIcon = MCP_PROVIDER_ICONS[providerName] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

  const chipSections: ChipSection[] = [];
  const metadataChips = [];

  if (providerName === 'github' && tool.tool_metadata?.repository) {
    metadataChips.push({
      key: 'repo',
      label: tool.tool_metadata.repository.full_name,
    });
  }

  if (providerName === 'jira' && tool.tool_metadata?.space_key) {
    metadataChips.push({
      key: 'space',
      label: `Space: ${tool.tool_metadata.space_key}`,
    });
  }

  if (metadataChips.length > 0) {
    chipSections.push({ label: 'Details', chips: metadataChips });
  }

  return (
    <EntityCard
      icon={providerIcon}
      title={tool.name}
      description={tool.description || 'No description provided'}
      statusLabel="Connected"
      statusColor="success"
      chipSections={chipSections}
      onClick={() => {
        const syntheticEvent = {
          stopPropagation: () => {},
        } as React.MouseEvent;
        onEdit(tool, syntheticEvent);
      }}
      onDelete={(e: React.MouseEvent) => onDelete(tool, e)}
    />
  );
}

interface AddToolCardProps {
  onClick: () => void;
}

export function AddToolCard({ onClick }: AddToolCardProps) {
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'action.hover',
        cursor: 'pointer',
        transition: 'all 0.2s',
        '&:hover': {
          bgcolor: 'action.selected',
          transform: 'translateY(-2px)',
        },
      }}
      onClick={onClick}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          p: 3.75,
          '&:last-child': { pb: 3.75 },
          gap: 1.5,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: 'primary.main',
          }}
        >
          <AddIcon />
        </Box>
        <Typography
          variant="subtitle1"
          component="div"
          sx={{ fontWeight: 700 }}
        >
          Add MCP
        </Typography>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Connect a new MCP provider
        </Typography>
        <Chip
          icon={<AddIcon />}
          label="New"
          size="small"
          variant="outlined"
          sx={{
            mt: 1,
            '& .MuiChip-icon': { color: 'text.secondary' },
            borderColor: 'divider',
            color: 'text.secondary',
          }}
        />
      </CardContent>
    </Card>
  );
}
