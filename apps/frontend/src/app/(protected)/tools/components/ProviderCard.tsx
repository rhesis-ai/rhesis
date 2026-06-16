'use client';

import React from 'react';
import { Button } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EntityCard from '@/components/common/EntityCard';
import { Tool, TypeLookup } from '@/utils/api-client/interfaces/tool';
import {
  TOOL_PROVIDER_ICONS,
  TOOL_PROVIDER_DESCRIPTIONS,
} from '@/config/tool-providers';

interface ProviderCardProps {
  providerType: TypeLookup;
  /** Existing connection for this provider, or null if not yet connected. */
  tool: Tool | null;
  onConnect: (providerType: TypeLookup) => void;
  onEdit: (tool: Tool) => void;
  onDelete: (tool: Tool) => void;
}

export function ProviderCard({
  providerType,
  tool,
  onConnect,
  onEdit,
  onDelete,
}: ProviderCardProps) {
  const providerKey = providerType.type_value;
  const icon = TOOL_PROVIDER_ICONS[providerKey] ?? <SmartToyIcon />;
  const displayName =
    providerKey.charAt(0).toUpperCase() + providerKey.slice(1);

  if (!tool) {
    return (
      <EntityCard
        icon={icon}
        title={displayName}
        description={TOOL_PROVIDER_DESCRIPTIONS[providerKey] ?? ''}
        footer={
          <Button
            variant="outlined"
            size="small"
            fullWidth
            onClick={() => onConnect(providerType)}
          >
            Connect
          </Button>
        }
      />
    );
  }

  return (
    <EntityCard
      icon={icon}
      title={displayName}
      description={tool.name}
      status="Connected"
      onClick={() => onEdit(tool)}
      onDelete={() => onDelete(tool)}
    />
  );
}
