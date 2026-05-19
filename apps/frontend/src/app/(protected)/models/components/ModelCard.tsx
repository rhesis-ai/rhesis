import React from 'react';
import { Box, IconButton, Chip, Tooltip, Button } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import WarningIcon from '@mui/icons-material/Warning';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SendIcon from '@mui/icons-material/Send';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { PROVIDER_ICONS } from '@/config/model-providers';
import type { ValidationStatus } from '../types';

interface ConnectedModelCardProps {
  model: Model;
  userSettings?: UserSettings | null;
  isVerified?: boolean;
  validationStatus?: ValidationStatus;
  /** Called when the edit icon is clicked — receives the originating mouse event for stopPropagation */
  onEdit: (model: Model, e: React.MouseEvent) => void;
  /** Called when delete is confirmed — EntityCard handles stopPropagation internally */
  onDelete: (model: Model) => void;
  onRequestAccess?: (model: Model) => void;
}

export function ConnectedModelCard({
  model,
  userSettings,
  isVerified = false,
  validationStatus,
  onEdit,
  onDelete,
  onRequestAccess,
}: ConnectedModelCardProps) {
  const theme = useTheme();

  const isGenerationDefault =
    userSettings?.models?.generation?.model_id === model.id;
  const isEvaluationDefault =
    userSettings?.models?.evaluation?.model_id === model.id;
  const isExecutionDefault =
    userSettings?.models?.execution?.model_id === model.id;
  const isEmbeddingDefault =
    userSettings?.models?.embedding?.model_id === model.id;
  const isAnyDefault =
    isGenerationDefault ||
    isEvaluationDefault ||
    isExecutionDefault ||
    isEmbeddingDefault;

  const showValidationError =
    validationStatus &&
    !validationStatus.isValid &&
    !validationStatus.isValidating;

  const isPolyphemus =
    model.provider_type?.type_value === 'polyphemus' ||
    model.icon === 'polyphemus' ||
    model.name?.toLowerCase().includes('polyphemus');

  const polyphemusAccess = userSettings?.polyphemus_access;
  const showPolyphemusRestricted = isPolyphemus && !isVerified;

  const hasRequestedAccess =
    !!polyphemusAccess?.requested_at &&
    !isVerified &&
    (!polyphemusAccess?.revoked_at ||
      polyphemusAccess.requested_at > polyphemusAccess.revoked_at);

  // Chip sections
  const chipSections: ChipSection[] = [];

  if (model.model_name) {
    chipSections.push({
      label: 'Model',
      chips: [{ key: 'model-name', label: model.model_name }],
    });
  }

  if (isAnyDefault) {
    const defaultChips = [
      isGenerationDefault ? { key: 'gen', label: 'Generation' } : null,
      isEvaluationDefault ? { key: 'eval', label: 'Evaluation' } : null,
      isExecutionDefault ? { key: 'exec', label: 'Execution' } : null,
      isEmbeddingDefault ? { key: 'embed', label: 'Embedding' } : null,
    ].filter((c): c is { key: string; label: string } => c !== null);

    chipSections.push({
      label: 'Default for',
      chips: defaultChips,
    });
  }

  // Footer: Polyphemus access button + "Access Required" badge (only when restricted)
  const footer = showPolyphemusRestricted ? (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {onRequestAccess && (
        <Button
          variant="outlined"
          size="small"
          fullWidth
          disabled={hasRequestedAccess}
          onClick={() => onRequestAccess(model)}
          color={hasRequestedAccess ? 'info' : 'primary'}
          startIcon={hasRequestedAccess ? <SendIcon /> : <VpnKeyIcon />}
        >
          {hasRequestedAccess ? 'Request Submitted' : 'Request Access'}
        </Button>
      )}

      <Chip
        icon={<CloseIcon />}
        label="Access Required"
        size="small"
        variant="outlined"
        sx={{
          width: '100%',
          color: 'warning.main',
          borderColor: 'warning.main',
          '& .MuiChip-icon': { color: 'warning.main', opacity: 0.7 },
        }}
      />
    </Box>
  ) : undefined;

  // Top-right actions: warning indicator + edit button (edit hidden for restricted Polyphemus)
  const hasTopActions = showValidationError || !showPolyphemusRestricted;
  const topRightActions = hasTopActions ? (
    <>
      {showValidationError && (
        <WarningIcon
          sx={{ fontSize: 16, color: 'warning.main', flexShrink: 0 }}
        />
      )}
      {!showPolyphemusRestricted && (
        <IconButton
          size="small"
          onClick={e => onEdit(model, e)}
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
      )}
    </>
  ) : undefined;

  const providerIcon = PROVIDER_ICONS[model.icon || 'custom'] ?? (
    <SmartToyIcon />
  );

  // Resolve warning color to a real CSS value for EntityCard's border template string
  const warningBorderColor = showValidationError
    ? theme.palette.warning.main
    : undefined;

  const card = (
    <EntityCard
      icon={providerIcon}
      title={model.name}
      description={model.description}
      onDelete={!model.is_protected ? () => onDelete(model) : undefined}
      topRightActions={topRightActions}
      chipSections={chipSections}
      footer={footer}
      borderColor={warningBorderColor}
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
