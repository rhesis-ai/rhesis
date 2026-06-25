'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
  useTheme,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import SettingsSuggestIcon from '@mui/icons-material/SettingsSuggest';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model } from '@/utils/api-client/interfaces/model';
import { PROVIDER_ICONS } from '@/config/model-providers';

type ModelPurpose = 'generation' | 'evaluation' | 'execution' | 'embedding';

interface ModelSelectorProps {
  sessionToken: string;
  value: string;
  onChange: (modelId: string) => void;
  label: string;
  purpose?: ModelPurpose;
  disabled?: boolean;
  helperText?: string;
  hideHelperText?: boolean;
  /** Plain text in the closed select — matches Figma drawer dropdowns. */
  compact?: boolean;
  /** Hide the secondary description line inside each dropdown item. */
  hideItemDescriptions?: boolean;
  /** Pre-fetched models list — skips the internal fetch when provided. */
  preloadedModels?: Model[];
  /** Whether the pre-fetched models are still loading. */
  isLoadingModels?: boolean;
  fieldSx?: SxProps<Theme>;
}

function ProviderIcon({ icon }: { icon?: string }) {
  if (!icon || !PROVIDER_ICONS[icon]) {
    return (
      <Box
        sx={{
          width: 20,
          height: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 20 }} />
      </Box>
    );
  }

  const providerIcon = PROVIDER_ICONS[icon];
  return (
    <Box
      sx={theme => {
        const size = theme.iconSizes?.small ?? 20;
        return {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          overflow: 'hidden',
          width: size,
          height: size,
          '& svg, & img': {
            width: size,
            height: size,
            maxWidth: size,
            maxHeight: size,
          },
        };
      }}
    >
      {providerIcon}
    </Box>
  );
}

export default function ModelSelector({
  sessionToken,
  value,
  onChange,
  label,
  purpose,
  disabled = false,
  helperText,
  hideHelperText = false,
  compact = false,
  hideItemDescriptions = false,
  preloadedModels,
  isLoadingModels: isLoadingModelsProp,
  fieldSx,
}: ModelSelectorProps) {
  const theme = useTheme();
  const [fetchedModels, setFetchedModels] = useState<Model[]>([]);
  const [isFetching, setIsFetching] = useState(false);
  const [defaultModelName, setDefaultModelName] = useState<string | null>(null);

  // If preloaded data is supplied, use it; otherwise fetch internally.
  const models = preloadedModels ?? fetchedModels;
  const isLoading =
    preloadedModels !== undefined ? (isLoadingModelsProp ?? false) : isFetching;

  useEffect(() => {
    // Skip internal fetch when the parent supplies preloaded data.
    if (preloadedModels !== undefined) {
      // Still resolve the default model name for the helper text.
      if (purpose && sessionToken) {
        const apiFactory = new ApiClientFactory(sessionToken);
        apiFactory
          .getUsersClient()
          .getUserSettings()
          .then(settings => {
            const defaultModelId = settings?.models?.[purpose]?.model_id;
            if (defaultModelId) {
              const match = preloadedModels.find(m => m.id === defaultModelId);
              setDefaultModelName(match?.name ?? null);
            }
          })
          .catch(() => {});
      }
      return;
    }

    const fetchData = async () => {
      try {
        setIsFetching(true);
        const apiFactory = new ApiClientFactory(sessionToken);
        const modelsClient = apiFactory.getModelsClient();
        const response = await modelsClient.getModels({
          sort_by: 'name',
          sort_order: 'asc',
          skip: 0,
          limit: 100,
        });
        const fetchedList = response.data || [];
        setFetchedModels(fetchedList);

        if (purpose) {
          try {
            const usersClient = apiFactory.getUsersClient();
            const settings = await usersClient.getUserSettings();
            const defaultModelId = settings?.models?.[purpose]?.model_id;
            if (defaultModelId) {
              const match = fetchedList.find(m => m.id === defaultModelId);
              setDefaultModelName(match?.name ?? null);
            }
          } catch {
            // User settings unavailable — leave default name unresolved
          }
        }
      } catch {
        setFetchedModels([]);
      } finally {
        setIsFetching(false);
      }
    };

    if (sessionToken) {
      fetchData();
    }
  }, [sessionToken, purpose, preloadedModels]);

  const selectedModel = models.find(m => m.id === value);

  const effectiveHelperText = (() => {
    const parts: string[] = [];
    if (helperText) parts.push(helperText);
    if (value === '') {
      if (defaultModelName) parts.push(`Currently: ${defaultModelName}`);
    } else if (selectedModel?.description) {
      parts.push(selectedModel.description);
    }
    return parts.join(' — ') || undefined;
  })();

  return (
    <Box>
      <FormControl fullWidth disabled={disabled} sx={fieldSx}>
        <InputLabel shrink>{label}</InputLabel>
        <Select
          value={value}
          label={label}
          onChange={e => onChange(e.target.value as string)}
          displayEmpty
          notched
          renderValue={selectedValue => {
            if (compact) {
              if (selectedValue === '') {
                const desc = defaultModelName
                  ? `Currently: ${defaultModelName}`
                  : 'Uses your configured default from model settings';
                return (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <SettingsSuggestIcon fontSize="small" />
                    <Box>
                      <Typography variant="body1">Default model</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {desc}
                      </Typography>
                    </Box>
                  </Box>
                );
              }
              const model = models.find(m => m.id === selectedValue);
              return (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ProviderIcon icon={model?.icon} />
                  <Box>
                    <Typography variant="body1">
                      {model?.name ?? String(selectedValue)}
                    </Typography>
                    {model?.description && (
                      <Typography variant="caption" color="text.secondary">
                        {model.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
              );
            }

            if (selectedValue === '') {
              return (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SettingsSuggestIcon fontSize="small" />
                  <Typography variant="body2">Default model</Typography>
                </Box>
              );
            }
            const model = models.find(m => m.id === selectedValue);
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ProviderIcon icon={model?.icon} />
                <Typography variant="body2">
                  {model?.name ?? (selectedValue as string)}
                </Typography>
              </Box>
            );
          }}
        >
          <MenuItem value="">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SettingsSuggestIcon fontSize="small" />
              <Box>
                <Typography variant="body2">Default model</Typography>
                {!hideItemDescriptions && (
                  <Typography variant="caption" color="text.secondary">
                    {defaultModelName
                      ? `Currently: ${defaultModelName}`
                      : 'Uses your configured default from model settings'}
                  </Typography>
                )}
              </Box>
            </Box>
          </MenuItem>
          {isLoading ? (
            <MenuItem disabled>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={theme.iconSizes?.small ?? 20} />
                <Typography variant="body2">Loading models...</Typography>
              </Box>
            </MenuItem>
          ) : (
            models.map(model => (
              <MenuItem key={model.id} value={model.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ProviderIcon icon={model.icon} />
                  <Box>
                    <Typography variant="body2">{model.name}</Typography>
                    {!hideItemDescriptions && model.description && (
                      <Typography variant="caption" color="text.secondary">
                        {model.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
              </MenuItem>
            ))
          )}
        </Select>
      </FormControl>
      {effectiveHelperText && !hideHelperText && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 0.5, display: 'block' }}
        >
          {effectiveHelperText}
        </Typography>
      )}
    </Box>
  );
}
