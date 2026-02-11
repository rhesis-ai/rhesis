import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Chip,
  Tooltip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import WarningIcon from '@mui/icons-material/Warning';
import { DeleteIcon, AddIcon } from '@/components/icons';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { PROVIDER_ICONS } from '@/config/model-providers';
import type { ValidationStatus } from '../types';

interface ConnectedModelCardProps {
  model: Model;
  userSettings?: UserSettings | null;
  validationStatus?: ValidationStatus;
  onEdit: (model: Model, e: React.MouseEvent) => void;
  onDelete: (model: Model, e: React.MouseEvent) => void;
}

export function ConnectedModelCard({
  model,
  userSettings,
  validationStatus,
  onEdit,
  onDelete,
}: ConnectedModelCardProps) {
  // Check if this model is set as default for generation, evaluation, or embedding
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

  const card = (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        ...(showValidationError && {
          borderColor: 'warning.main',
          borderWidth: 1,
          borderStyle: 'solid',
        }),
      }}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
        }}
      >
        {/* Action buttons */}
        <Box
          sx={{
            position: 'absolute',
            top: theme => theme.spacing(1),
            right: theme => theme.spacing(1),
            display: 'flex',
            gap: theme => theme.spacing(0.5),
            zIndex: 1,
          }}
        >
          {/* Allow editing settings for all models, but only show delete for non-protected */}
          <IconButton
            size="small"
            onClick={e => onEdit(model, e)}
            sx={{
              padding: '2px',
              '& .MuiSvgIcon-root': {
                fontSize: theme =>
                  theme?.typography?.helperText?.fontSize || '0.75rem',
                color: 'currentColor',
              },
            }}
          >
            <EditIcon fontSize="inherit" />
          </IconButton>
          {!model.is_protected && (
            <IconButton
              size="small"
              onClick={e => onDelete(model, e)}
              sx={{
                padding: '2px',
                '& .MuiSvgIcon-root': {
                  fontSize: theme =>
                    theme?.typography?.helperText?.fontSize || '0.75rem',
                  color: 'currentColor',
                },
              }}
            >
              <DeleteIcon fontSize="inherit" />
            </IconButton>
          )}
        </Box>

        <Box>
          {/* Model header */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                display: 'flex',
                alignItems: 'center',
                color: 'primary.main',
              }}
            >
              {PROVIDER_ICONS[model.icon || 'custom'] || <SmartToyIcon />}
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
              }}
            >
              {model.name}
            </Typography>
            {showValidationError && (
              <WarningIcon
                sx={{
                  ml: 1,
                  fontSize: theme => theme.iconSizes.small,
                  color: 'warning.main',
                }}
              />
            )}
          </Box>

          {/* Model description and details */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            {model.description}
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          {/* Default indicator */}
          {isAnyDefault && (
            <Typography
              variant="caption"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                mb: 0.5,
                fontWeight: 500,
                color: 'primary.main',
              }}
            >
              <BookmarkBorderIcon
                sx={{
                  fontSize: theme => theme?.typography?.caption?.fontSize,
                }}
              />
              <Box component="span">
                Default:{' '}
                {isGenerationDefault && isEvaluationDefault
                  ? 'Generation & Evaluation'
                  : isGenerationDefault
                    ? 'Generation'
                    : isEvaluationDefault
                      ? 'Evaluation'
                      : 'Embedding'}
              </Box>
            </Typography>
          )}

          {/* Model name */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 1.5,
              minHeight: '1.5em',
            }}
          >
            Model: {model.model_name}
          </Typography>

          {/* Connected status or System badge */}
          <Chip
            icon={<CheckCircleIcon />}
            label={model.is_protected ? 'Rhesis Managed' : 'Connected'}
            size="small"
            variant="outlined"
            sx={{
              width: '100%',
              color: 'text.secondary',
              borderColor: model.is_protected ? 'info.main' : 'divider',
              '& .MuiChip-icon': {
                color: model.is_protected ? 'info.main' : 'primary.main',
                opacity: 0.7,
              },
            }}
          />
        </Box>
      </CardContent>
    </Card>
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
        {card}
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
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
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
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
              }}
            >
              Add Model
            </Typography>
          </Box>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            Connect a new model
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 1.5,
              minHeight: '1.5em',
            }}
          >
            {/* Empty space for alignment */}
          </Typography>

          <Chip
            icon={<AddIcon />}
            label="New"
            size="small"
            variant="outlined"
            sx={{
              width: '100%',
              '& .MuiChip-icon': {
                color: 'text.secondary',
              },
              borderColor: 'divider',
              color: 'text.secondary',
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
}
