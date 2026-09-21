'use client';

import React, { useMemo } from 'react';
import { Box, ButtonBase, Skeleton, Stack, Typography } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import {
  TOOL_PROVIDER_ICONS,
  formatToolProviderDisplayName,
} from '@/config/tool-providers';
import type { TypeLookup } from '@/utils/api-client/interfaces/tool';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';

/** One tile: the lookup row the backend needs, plus how to describe it. */
export interface ProviderChoice {
  /** `TypeLookup.id` — what `tool_provider_type_id` is set to on save. */
  id: string;
  key: string;
  displayName: string;
  description: string;
}

/**
 * Join the provider lookups with their manifests.
 *
 * A tool is saved against a `type_lookup` row, so the UUID has to come from
 * there; everything shown on the tile comes from the manifest. A lookup with no
 * manifest is dropped: the backend would reject a tool for it anyway, and a
 * tile that cannot be connected is worse than no tile.
 */
export function buildProviderChoices(
  lookups: TypeLookup[],
  providers: ToolProvider[]
): ProviderChoice[] {
  const byKey = new Map(providers.map(p => [p.key, p]));
  return lookups
    .flatMap(lookup => {
      const manifest = byKey.get(lookup.type_value);
      if (!manifest) return [];
      return [
        {
          id: lookup.id as string,
          key: lookup.type_value,
          displayName: manifest.display_name,
          description: manifest.description,
        },
      ];
    })
    .sort((a, b) => a.displayName.localeCompare(b.displayName));
}

interface ProviderPickerProps {
  lookups: TypeLookup[];
  providers: ToolProvider[];
  loading?: boolean;
  selectedId?: string | null;
  onSelect: (choice: ProviderChoice) => void;
}

const SKELETON_TILES = 6;

export function ProviderPicker({
  lookups,
  providers,
  loading = false,
  selectedId,
  onSelect,
}: ProviderPickerProps) {
  const choices = useMemo(
    () => buildProviderChoices(lookups, providers),
    [lookups, providers]
  );

  if (loading) {
    return (
      <Box sx={gridSx}>
        {Array.from({ length: SKELETON_TILES }, (_, i) => (
          <Skeleton
            key={`provider-skeleton-${i}`}
            variant="rounded"
            height={104}
          />
        ))}
      </Box>
    );
  }

  if (choices.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No tool providers are available on this deployment.
      </Typography>
    );
  }

  return (
    <Box sx={gridSx} role="radiogroup" aria-label="Tool provider">
      {choices.map(choice => {
        const selected = choice.id === selectedId;
        return (
          <ButtonBase
            key={choice.id}
            role="radio"
            aria-checked={selected}
            aria-label={choice.displayName}
            onClick={() => onSelect(choice)}
            sx={theme => ({
              display: 'block',
              textAlign: 'left',
              width: '100%',
              height: '100%',
              p: 2,
              borderRadius: BORDER_RADIUS.md,
              border: '1px solid',
              borderColor: selected ? 'primary.main' : 'divider',
              backgroundColor: selected
                ? theme.palette.action.selected
                : 'background.paper',
              transition: theme.transitions.create([
                'border-color',
                'box-shadow',
              ]),
              '&:hover': {
                borderColor: 'primary.main',
                boxShadow: ELEVATION.xs,
              },
              '&:focus-visible': {
                outline: '2px solid',
                outlineColor: theme.palette.primary.main,
              },
            })}
          >
            <Stack spacing={1}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  color: 'text.primary',
                }}
              >
                {/* An icon the frontend does not know about still renders a
                    usable tile: a backend newer than this build can serve a
                    provider whose logo ships later. */}
                {TOOL_PROVIDER_ICONS[choice.key] ?? (
                  <SmartToyIcon fontSize="small" />
                )}
                <Typography variant="subtitle2" component="span">
                  {choice.displayName ||
                    formatToolProviderDisplayName(choice.key)}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {choice.description}
              </Typography>
            </Stack>
          </ButtonBase>
        );
      })}
    </Box>
  );
}

const gridSx = {
  display: 'grid',
  gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
  gap: 2,
} as const;
