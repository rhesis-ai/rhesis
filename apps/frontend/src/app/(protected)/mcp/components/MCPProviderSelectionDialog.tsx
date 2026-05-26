import React from 'react';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import {
  ProviderSelectionDialog as BaseProviderSelectionDialog,
  type ProviderDialogItem,
} from '@/components/common/ProviderSelectionDialog';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface MCPProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
}

const PROVIDER_ORDER: Record<string, number> = {
  notion: 1,
  github: 2,
  jira: 3,
  confluence: 4,
  custom: 5,
};

const ENABLED_MCP_PROVIDERS = new Set([
  'notion',
  'github',
  'jira',
  'confluence',
  'custom',
]);

function mcpProviderDisplayName(typeValue: string): string {
  switch (typeValue) {
    case 'notion':
      return 'Notion';
    case 'github':
      return 'GitHub';
    case 'jira':
      return 'Jira';
    case 'confluence':
      return 'Confluence';
    case 'atlassian':
      return 'Atlassian';
    case 'custom':
      return 'Custom provider';
    default:
      return typeValue;
  }
}

function buildMcpProviderItems(providers: TypeLookup[]): ProviderDialogItem[] {
  const sorted = [...providers].sort((a, b) => {
    const aOrder = PROVIDER_ORDER[a.type_value] ?? 999;
    const bOrder = PROVIDER_ORDER[b.type_value] ?? 999;
    return aOrder - bOrder;
  });

  return sorted.map(provider => {
    const isCustom = provider.type_value === 'custom';
    const isEnabled = ENABLED_MCP_PROVIDERS.has(provider.type_value);
    const chips: ProviderDialogItem['chips'] = [];
    if (isCustom) chips.push({ label: 'Advanced' });
    if (!isEnabled && !isCustom) chips.push({ label: 'Coming Soon' });

    return {
      provider,
      name: mcpProviderDisplayName(provider.type_value),
      icon: MCP_PROVIDER_ICONS[provider.type_value] || (
        <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
      ),
      enabled: isEnabled,
      chips: chips.length > 0 ? chips : undefined,
    };
  });
}

export function MCPProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
}: MCPProviderSelectionDialogProps) {
  const items = buildMcpProviderItems(providers);

  return (
    <BaseProviderSelectionDialog
      open={open}
      onClose={onClose}
      onSelectProvider={onSelectProvider}
      title="Select MCP Provider"
      items={items}
    />
  );
}
