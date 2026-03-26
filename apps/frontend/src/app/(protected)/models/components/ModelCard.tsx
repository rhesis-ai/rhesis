import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Tooltip,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import { AddIcon } from '@/components/icons';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { PROVIDER_ICONS } from '@/config/model-providers';
import type { ValidationStatus } from '../types';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';

interface ConnectedModelCardProps {
  model: Model;
  userSettings?: UserSettings | null;
  isVerified?: boolean;
  validationStatus?: ValidationStatus;
  onEdit: (model: Model, e: React.MouseEvent) => void;
  onDelete: (model: Model, e: React.MouseEvent) => void;
  onRequestAccess?: (model: Model) => void;
}

export function ConnectedModelCard({
  model,
  userSettings,
  isVerified = false,
  validationStatus,
  onEdit,
  onDelete,
}: ConnectedModelCardProps) {
  const isGenerationDefault =
    userSettings?.models?.generation?.model_id === model.id;
  const isEvaluationDefault =
    userSettings?.models?.evaluation?.model_id === model.id;
  const isEmbeddingDefault =
    userSettings?.models?.embedding?.model_id === model.id;
  const isAnyDefault =
    isGenerationDefault || isEvaluationDefault || isEmbeddingDefault;

  const showValidationError =
    validationStatus &&
    !validationStatus.isValid &&
    !validationStatus.isValidating;

  const isPolyphemus =
    model.provider_type?.type_value === 'polyphemus' ||
    model.icon === 'polyphemus' ||
    model.name?.toLowerCase().includes('polyphemus');

  const showPolyphemusRestricted = isPolyphemus && !isVerified;

  let statusLabel: string;
  let statusColor: 'success' | 'warning' | 'error' | 'info' | 'default';
  if (showPolyphemusRestricted) {
    statusLabel = 'Access Required';
    statusColor = 'warning';
  } else if (model.is_protected) {
    statusLabel = 'Rhesis Managed';
    statusColor = 'info';
  } else {
    statusLabel = 'Connected';
    statusColor = 'success';
  }

  const chipSections: ChipSection[] = [];
  const detailChips = [];

  if (model.model_name) {
    detailChips.push({ key: 'model-name', label: model.model_name });
  }

  if (isAnyDefault) {
    const defaultLabel =
      isGenerationDefault && isEvaluationDefault
        ? 'Generation & Evaluation'
        : isGenerationDefault
          ? 'Generation'
          : isEvaluationDefault
            ? 'Evaluation'
            : 'Embedding';
    detailChips.push({
      key: 'default',
      icon: <BookmarkBorderIcon fontSize="small" />,
      label: `Default: ${defaultLabel}`,
    });
  }

  if (detailChips.length > 0) {
    chipSections.push({ label: 'Details', chips: detailChips });
  }

  const providerIcon = PROVIDER_ICONS[model.icon || 'custom'] || (
    <SmartToyIcon />
  );

  const card = (
    <EntityCard
      icon={providerIcon}
      title={model.name}
      description={model.description || 'No description provided'}
      statusLabel={statusLabel}
      statusColor={statusColor}
      chipSections={chipSections}
      onClick={() => {
        const syntheticEvent = {
          stopPropagation: () => {},
        } as React.MouseEvent;
        if (!showPolyphemusRestricted) {
          onEdit(model, syntheticEvent);
        }
      }}
      onDelete={
        !model.is_protected
          ? (e: React.MouseEvent) => onDelete(model, e)
          : undefined
      }
    />
  );

  if (showValidationError) {
    return (
      <Tooltip
        title={
          validationStatus?.errorMessage ||
          'Configuration required: Please configure a valid Rhesis API key'
        }
        placement="top"
        arrow
      >
        <Box sx={{ height: '100%' }}>{card}</Box>
      </Tooltip>
    );
  }

  return card;
}

interface AddModelCardProps {
  onClick: () => void;
}

export function AddModelCard({ onClick }: AddModelCardProps) {
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
          Add Model
        </Typography>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Connect a new model
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
