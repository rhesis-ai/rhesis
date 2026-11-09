import React from 'react';
import { Box, Tooltip, Button } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import WarningIcon from '@mui/icons-material/Warning';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SendIcon from '@mui/icons-material/Send';
import EntityCard, {
  type EntityCardFact,
} from '@/components/common/EntityCard';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import {
  PROVIDER_ICONS,
  getProviderDisplayName,
} from '@/config/model-providers';
import type { ModelType } from '@/constants/model-types';
import { getAvailabilityReasonCopy, type ValidationStatus } from '../types';
import { useIsLocalMode } from '@/contexts/FeaturesContext';

const MODEL_TYPE_LABELS: Record<ModelType, string> = {
  language: 'Language',
  embedding: 'Embedding',
  decision: 'Decision',
};

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

  const defaultFor = [
    isGenerationDefault && 'Generation',
    isEvaluationDefault && 'Evaluation',
    isExecutionDefault && 'Execution',
    isEmbeddingDefault && 'Embedding',
  ].filter((label): label is string => !!label);

  const facts: EntityCardFact[] = [];
  if (model.model_type) {
    facts.push({
      key: 'model-type',
      kind: 'type',
      label: MODEL_TYPE_LABELS[model.model_type] ?? model.model_type,
    });
  }
  if (showPolyphemusRestricted) {
    facts.push({ key: 'access', kind: 'state', label: 'Access needed' });
  } else if (model.model_name) {
    facts.push({
      key: 'model-name',
      kind: 'plain',
      label: model.model_name,
      mono: true,
    });
  }

  const footerAction =
    showPolyphemusRestricted &&
    onRequestAccess &&
    canRequestPolyphemusAccess ? (
      <Button
        size="small"
        disabled={hasRequestedAccess}
        onClick={() => onRequestAccess(model)}
        startIcon={hasRequestedAccess ? <SendIcon /> : <VpnKeyIcon />}
      >
        {hasRequestedAccess ? 'Request submitted' : 'Request access'}
      </Button>
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
      context={
        model.provider_type
          ? getProviderDisplayName(model.provider_type)
          : undefined
      }
      facts={facts}
      relations={[
        defaultFor.length > 0
          ? {
              key: 'default-for',
              label: `Default for ${defaultFor.join(', ')}`,
            }
          : { key: 'default-for', label: 'Not a default', muted: true },
      ]}
      footerAction={footerAction}
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
