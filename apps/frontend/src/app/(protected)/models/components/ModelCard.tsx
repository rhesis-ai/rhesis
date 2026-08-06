import React from 'react';
import { Box, Chip, Tooltip, Button } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import WarningIcon from '@mui/icons-material/Warning';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SendIcon from '@mui/icons-material/Send';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { PROVIDER_ICONS } from '@/config/model-providers';
import { getAvailabilityReasonCopy, type ValidationStatus } from '../types';
import { useIsLocalMode } from '@/contexts/FeaturesContext';

interface ConnectedModelCardProps {
  model: Model;
  userSettings?: UserSettings | null;
  isVerified?: boolean;
  validationStatus?: ValidationStatus;
  /** Opens the edit connection dialog when the card is clicked */
  onCardClick?: (model: Model) => void;
  /** Called when delete is confirmed — EntityCard handles stopPropagation internally */
  onDelete?: (model: Model) => void;
  onRequestAccess?: (model: Model) => void;
}

export function ConnectedModelCard({
  model,
  userSettings,
  isVerified = false,
  validationStatus,
  onCardClick,
  onDelete,
  onRequestAccess,
}: ConnectedModelCardProps) {
  const theme = useTheme();
  const isLocalMode = useIsLocalMode();

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

  // Backend-reported availability takes precedence over the client-side
  // validation/polyphemus states below, so we never surface two conflicting
  // reasons on the same card. `available` defaults to true when omitted.
  const isUnavailable = model.available === false;
  const availabilityReason = getAvailabilityReasonCopy(
    model.availability_reason
  );

  const showValidationError =
    !isUnavailable &&
    validationStatus &&
    !validationStatus.isValid &&
    !validationStatus.isValidating;

  const isPolyphemus =
    model.provider_type?.type_value === 'polyphemus' ||
    model.icon === 'polyphemus' ||
    model.name?.toLowerCase().includes('polyphemus');

  const polyphemusAccess = userSettings?.polyphemus_access;
  // Suppress the polyphemus "request access" affordance when the backend has
  // already greyed the card out (the availability tooltip is the single
  // authoritative explanation then) and in local mode (no email to request
  // through — availability alone gates the card).
  const showPolyphemusRestricted =
    !isLocalMode && !isUnavailable && isPolyphemus && !isVerified;

  const hasRequestedAccess =
    !!polyphemusAccess?.requested_at &&
    !isVerified &&
    (!polyphemusAccess?.revoked_at ||
      polyphemusAccess.requested_at > polyphemusAccess.revoked_at);

  const canRequestPolyphemusAccess = can(
    userSettings,
    Capability.Polyphemus.REQUEST
  );

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
    <Box
      sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}
      onClick={e => e.stopPropagation()}
    >
      {onRequestAccess && canRequestPolyphemusAccess && (
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

  const topRightActions = showValidationError ? (
    <WarningIcon sx={{ fontSize: 16, color: 'warning.main', flexShrink: 0 }} />
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
      onClick={
        !isUnavailable && !showPolyphemusRestricted && onCardClick
          ? () => onCardClick(model)
          : undefined
      }
      onDelete={
        !model.is_protected && onDelete ? () => onDelete(model) : undefined
      }
      topRightActions={topRightActions}
      chipSections={chipSections}
      footer={footer}
      borderColor={warningBorderColor}
    />
  );

  if (isUnavailable) {
    return (
      <Tooltip title={availabilityReason} placement="top" arrow>
        <Box
          sx={{
            height: '100%',
            opacity: 0.5,
            cursor: 'not-allowed',
            // Block interaction with the greyed-out card while keeping the
            // wrapper hoverable so the reason tooltip still appears.
            '& *': { pointerEvents: 'none' },
          }}
        >
          {card}
        </Box>
      </Tooltip>
    );
  }

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
