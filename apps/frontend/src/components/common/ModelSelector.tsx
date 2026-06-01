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
}

function ProviderIcon({ icon }: { icon?: string }) {
  if (!icon || !PROVIDER_ICONS[icon]) {
    return <SmartToyIcon fontSize="small" />;
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
          width: size,
          height: size,
          '& svg, & img': {
            width: size,
            height: size,
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
}: ModelSelectorProps) {
  const theme = useTheme();
  const [models, setModels] = useState<Model[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [defaultModelName, setDefaultModelName] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const apiFactory = new ApiClientFactory(sessionToken);
        const modelsClient = apiFactory.getModelsClient();
        const response = await modelsClient.getModels({
          sort_by: 'name',
          sort_order: 'asc',
          skip: 0,
          limit: 100,
        });
        const fetchedModels = response.data || [];
        setModels(fetchedModels);

        if (purpose) {
          try {
            const usersClient = apiFactory.getUsersClient();
            const settings = await usersClient.getUserSettings();
            const defaultModelId = settings?.models?.[purpose]?.model_id;
            if (defaultModelId) {
              const match = fetchedModels.find(m => m.id === defaultModelId);
              setDefaultModelName(match?.name ?? null);
            }
          } catch {
            // User settings unavailable — leave default name unresolved
          }
        }
      } catch {
        setModels([]);
      } finally {
        setIsLoading(false);
      }
    };

    if (sessionToken) {
      fetchData();
    }
  }, [sessionToken, purpose]);

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
      <FormControl fullWidth disabled={disabled}>
        <InputLabel shrink>{label}</InputLabel>
        <Select
          value={value}
          label={label}
          onChange={e => onChange(e.target.value as string)}
          displayEmpty
          renderValue={selectedValue => {
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
                <Typography variant="caption" color="text.secondary">
                  {defaultModelName
                    ? `Currently: ${defaultModelName}`
                    : 'Uses your configured default from model settings'}
                </Typography>
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
                    {model.description && (
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
      {effectiveHelperText && (
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
